"""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║   ⚡ CYBERHOST v2.0 - HOSPEDAGEM WEB PROFISSIONAL           ║
║   Git Pobre • Deploy Automático • Multi-Usuário            ║
║   PHP • Python • JavaScript • HTML • CSS                   ║
║                                                              ║
║   By @cybersecofc                                           ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
"""

import os
import sys
import json
import time
import uuid
import random
import shutil
import hashlib
import secrets
import threading
import subprocess
import zipfile
import io
import re as regex
from datetime import datetime
from pathlib import Path
from functools import wraps
from typing import Dict, List, Any, Optional
from werkzeug.utils import secure_filename

# ============================================
# INSTALAÇÃO AUTOMÁTICA
# ============================================
def install_package(package):
    try:
        __import__(package.replace('-', '_').replace('.', '_'))
    except ImportError:
        print(f"[INSTALANDO] {package}...")
        os.system(f"{sys.executable} -m pip install {package} --quiet --no-warn-script-location")
        print(f"[OK] {package}")

print("=" * 60)
print("⚡ CYBERHOST v2.0 - INICIANDO SISTEMA")
print("=" * 60)

DEPS = ['flask', 'flask-cors', 'werkzeug', 'requests', 'colorama']
for dep in DEPS:
    install_package(dep)

from flask import (Flask, render_template_string, jsonify, request, 
                   redirect, url_for, session, send_file, send_from_directory,
                   make_response, Response)
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import requests as http_requests
from colorama import init, Fore, Style

init(autoreset=True)

# ============================================
# CONFIGURAÇÕES
# ============================================
class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', secrets.token_hex(32))
    PORT = int(os.environ.get('PORT', 5000))
    BASE_URL = os.environ.get('RENDER_EXTERNAL_URL', f'http://localhost:{PORT}')
    ADMIN_USER = "cyber"
    ADMIN_PASS = "cybersecofcadm"
    VERSION = "2.0.0"
    
    # Diretórios
    DATA_DIR = 'cyberhost_data'
    USERS_DIR = f'{DATA_DIR}/users'
    REPOS_DIR = f'{DATA_DIR}/repos'
    DEPLOYS_DIR = f'{DATA_DIR}/deploys'
    LOGS_DIR = f'{DATA_DIR}/logs'
    
    # Arquivos de dados
    USERS_FILE = f'{DATA_DIR}/users.json'
    REPOS_FILE = f'{DATA_DIR}/repos.json'
    DEPLOYS_FILE = f'{DATA_DIR}/deploys.json'
    SETTINGS_FILE = f'{DATA_DIR}/settings.json'
    
    ALLOWED_EXTENSIONS = {
        'php', 'py', 'js', 'html', 'htm', 'css', 'json', 'txt', 'md', 
        'xml', 'htaccess', 'env', 'gitignore', 'yml', 'yaml', 'toml',
        'jpg', 'jpeg', 'png', 'gif', 'svg', 'ico', 'webp',
        'woff', 'woff2', 'ttf', 'eot', 'mp4', 'webm', 'mp3', 'wav'
    }

# Criar diretórios
for d in [Config.DATA_DIR, Config.USERS_DIR, Config.REPOS_DIR, 
          Config.DEPLOYS_DIR, Config.LOGS_DIR]:
    os.makedirs(d, exist_ok=True)

# ============================================
# BANCO DE DADOS
# ============================================
class Database:
    def __init__(self):
        self.users = self._load(Config.USERS_FILE)
        self.repos = self._load(Config.REPOS_FILE)
        self.deploys = self._load(Config.DEPLOYS_FILE)
        self.settings = self._load(Config.SETTINGS_FILE, {'site_name': 'CyberHost', 'max_repos': 50})
        self._init_admin()
    
    def _load(self, filename, default=None):
        if os.path.exists(filename):
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return default if default is not None else {}
        return default if default is not None else {}
    
    def _save(self, filename, data):
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def _init_admin(self):
        if Config.ADMIN_USER not in self.users:
            self.users[Config.ADMIN_USER] = {
                'password': generate_password_hash(Config.ADMIN_PASS),
                'is_admin': True,
                'created_at': datetime.now().isoformat(),
                'email': 'admin@cyberhost.com',
                'plan': 'admin',
                'blocked': False,
                'repos_count': 0,
                'deploys_count': 0
            }
            self._save(Config.USERS_FILE, self.users)
    
    def create_user(self, username, password, email):
        if username in self.users:
            return False, "Usuário já existe!"
        
        self.users[username] = {
            'password': generate_password_hash(password),
            'is_admin': False,
            'created_at': datetime.now().isoformat(),
            'email': email,
            'plan': 'free',
            'blocked': False,
            'repos_count': 0,
            'deploys_count': 0
        }
        
        os.makedirs(f'{Config.REPOS_DIR}/{username}', exist_ok=True)
        os.makedirs(f'{Config.DEPLOYS_DIR}/{username}', exist_ok=True)
        
        self._save(Config.USERS_FILE, self.users)
        return True, "Conta criada com sucesso!"
    
    def authenticate(self, username, password):
        user = self.users.get(username)
        if not user:
            return False, "Usuário não encontrado!"
        if user.get('blocked'):
            return False, "Conta bloqueada!"
        if not check_password_hash(user['password'], password):
            return False, "Senha incorreta!"
        return True, user
    
    def create_repo(self, username, repo_name, description="", language="html"):
        repo_id = uuid.uuid4().hex[:12]
        repo_path = f'{Config.REPOS_DIR}/{username}/{repo_name}'
        
        existing = [r for r in self.repos.values() if r['owner'] == username and r['name'] == repo_name]
        if existing:
            return False, "Repositório já existe!"
        
        os.makedirs(repo_path, exist_ok=True)
        
        # Criar arquivo inicial baseado na linguagem
        initial_files = {
            'html': ('index.html', '<!DOCTYPE html>\n<html>\n<head>\n    <title>Meu Site</title>\n</head>\n<body>\n    <h1>Olá Mundo!</h1>\n    <p>Site hospedado no CyberHost</p>\n</body>\n</html>'),
            'python': ('main.py', 'from flask import Flask\n\napp = Flask(__name__)\n\n@app.route("/")\ndef home():\n    return "Olá Mundo! Site hospedado no CyberHost"\n\nif __name__ == "__main__":\n    app.run(host="0.0.0.0", port=5000)'),
            'php': ('index.php', '<?php\necho "<h1>Olá Mundo!</h1>";\necho "<p>Site hospedado no CyberHost</p>";\n?>'),
            'javascript': ('index.js', 'console.log("Olá Mundo! Site hospedado no CyberHost");'),
        }
        
        if language in initial_files:
            filename, content = initial_files[language]
            with open(f'{repo_path}/{filename}', 'w', encoding='utf-8') as f:
                f.write(content)
        
        # Criar README
        with open(f'{repo_path}/README.md', 'w', encoding='utf-8') as f:
            f.write(f'# {repo_name}\n\n{description}\n\nHospedado no CyberHost')
        
        self.repos[repo_id] = {
            'id': repo_id,
            'owner': username,
            'name': repo_name,
            'description': description,
            'path': repo_path,
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat(),
            'language': language,
            'is_public': True,
            'deploy_url': None,
            'deploy_status': 'not_deployed',
            'views': 0
        }
        
        self.users[username]['repos_count'] = self.users[username].get('repos_count', 0) + 1
        self._save(Config.REPOS_FILE, self.repos)
        self._save(Config.USERS_FILE, self.users)
        
        # Log
        self._log(username, f"Criou repositório: {repo_name}")
        
        return True, repo_id
    
    def delete_repo(self, repo_id, username):
        repo = self.repos.get(repo_id)
        if not repo or repo['owner'] != username:
            return False
        
        if os.path.exists(repo['path']):
            shutil.rmtree(repo['path'], ignore_errors=True)
        
        if repo.get('deploy_url'):
            deploy_path = f'{Config.DEPLOYS_DIR}/{username}/{repo["name"]}'
            if os.path.exists(deploy_path):
                shutil.rmtree(deploy_path, ignore_errors=True)
        
        del self.repos[repo_id]
        self.users[username]['repos_count'] = max(0, self.users[username].get('repos_count', 1) - 1)
        self._save(Config.REPOS_FILE, self.repos)
        self._save(Config.USERS_FILE, self.users)
        self._log(username, f"Deletou repositório: {repo['name']}")
        return True
    
    def deploy_repo(self, repo_id, username, subdomain):
        repo = self.repos.get(repo_id)
        if not repo or repo['owner'] != username:
            return False, "Repositório não encontrado!"
        
        subdomain = regex.sub(r'[^a-z0-9-]', '', subdomain.lower())
        if not subdomain:
            subdomain = f"{username}-{repo['name']}"
        
        deploy_url = f"cyber-{subdomain}.onrender.com"
        deploy_path = f'{Config.DEPLOYS_DIR}/{username}/{repo["name"]}'
        
        # Limpar deploy anterior
        if os.path.exists(deploy_path):
            shutil.rmtree(deploy_path)
        
        # Copiar arquivos
        shutil.copytree(repo['path'], deploy_path)
        
        # Instalar dependências Python se existir
        requirements = f'{deploy_path}/requirements.txt'
        if os.path.exists(requirements):
            try:
                subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', requirements],
                             capture_output=True, timeout=120)
            except:
                pass
        
        repo['deploy_url'] = deploy_url
        repo['deploy_status'] = 'deployed'
        repo['updated_at'] = datetime.now().isoformat()
        
        self.users[username]['deploys_count'] = self.users[username].get('deploys_count', 0) + 1
        self._save(Config.REPOS_FILE, self.repos)
        self._save(Config.USERS_FILE, self.users)
        self._log(username, f"Deploy: {repo['name']} -> {deploy_url}")
        
        return True, deploy_url
    
    def get_user_repos(self, username):
        return {k: v for k, v in self.repos.items() if v['owner'] == username}
    
    def _log(self, username, action):
        log_file = f'{Config.LOGS_DIR}/{datetime.now().strftime("%Y-%m-%d")}.log'
        entry = f"[{datetime.now().isoformat()}] [{username}] {action}\n"
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(entry)

db = Database()

# ============================================
# GIT POBRE - SISTEMA DE VERSIONAMENTO
# ============================================
class GitPobre:
    """Sistema Git Pobre - Versionamento sem Git externo"""
    
    @staticmethod
    def get_files(username, repo_name, path=""):
        """Lista arquivos do repositório"""
        repo_path = f'{Config.REPOS_DIR}/{username}/{repo_name}/{path}'
        if not os.path.exists(repo_path):
            return []
        
        files = []
        try:
            for item in os.listdir(repo_path):
                if item.startswith('.cybergit'):
                    continue
                
                item_path = os.path.join(repo_path, item)
                rel_path = os.path.join(path, item) if path else item
                
                if os.path.isfile(item_path):
                    ext = item.split('.')[-1] if '.' in item else ''
                    files.append({
                        'name': item,
                        'path': rel_path.replace('\\', '/'),
                        'type': 'file',
                        'size': os.path.getsize(item_path),
                        'extension': ext,
                        'modified': datetime.fromtimestamp(os.path.getmtime(item_path)).strftime('%d/%m/%Y %H:%M')
                    })
                elif os.path.isdir(item_path):
                    files.append({
                        'name': item,
                        'path': rel_path.replace('\\', '/'),
                        'type': 'folder',
                        'size': 0,
                        'modified': ''
                    })
        except Exception as e:
            print(f"Erro ao listar arquivos: {e}")
        
        return sorted(files, key=lambda x: (x['type'] != 'folder', x['name'].lower()))
    
    @staticmethod
    def get_file_content(username, repo_name, file_path):
        """Lê conteúdo de um arquivo"""
        full_path = f'{Config.REPOS_DIR}/{username}/{repo_name}/{file_path}'
        if not os.path.exists(full_path) or not os.path.isfile(full_path):
            return None
        
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                return f.read()
        except:
            try:
                with open(full_path, 'r', encoding='latin-1') as f:
                    return f.read()
            except:
                return "[Arquivo binário]"
    
    @staticmethod
    def save_file(username, repo_name, file_path, content):
        """Salva ou atualiza um arquivo"""
        full_path = f'{Config.REPOS_DIR}/{username}/{repo_name}/{file_path}'
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        
        try:
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # Atualizar timestamp do repo
            repo = db.repos.get([k for k, v in db.repos.items() 
                                if v['owner'] == username and v['name'] == repo_name][0] 
                                if [k for k, v in db.repos.items() 
                                    if v['owner'] == username and v['name'] == repo_name] else None)
            if repo:
                repo_id = [k for k, v in db.repos.items() 
                          if v['owner'] == username and v['name'] == repo_name][0]
                db.repos[repo_id]['updated_at'] = datetime.now().isoformat()
                db._save(Config.REPOS_FILE, db.repos)
            
            return True, "Arquivo salvo com sucesso!"
        except Exception as e:
            return False, str(e)
    
    @staticmethod
    def delete_file(username, repo_name, file_path):
        """Deleta um arquivo ou pasta"""
        full_path = f'{Config.REPOS_DIR}/{username}/{repo_name}/{file_path}'
        if not os.path.exists(full_path):
            return False, "Arquivo não encontrado!"
        
        try:
            if os.path.isfile(full_path):
                os.remove(full_path)
            else:
                shutil.rmtree(full_path, ignore_errors=True)
            return True, "Deletado com sucesso!"
        except Exception as e:
            return False, str(e)
    
    @staticmethod
    def create_folder(username, repo_name, folder_path):
        """Cria uma pasta"""
        full_path = f'{Config.REPOS_DIR}/{username}/{repo_name}/{folder_path}'
        try:
            os.makedirs(full_path, exist_ok=True)
            return True, "Pasta criada!"
        except Exception as e:
            return False, str(e)
    
    @staticmethod
    def upload_file(username, repo_name, file, subpath=""):
        """Upload de arquivo"""
        if subpath:
            full_path = f'{Config.REPOS_DIR}/{username}/{repo_name}/{subpath}'
        else:
            full_path = f'{Config.REPOS_DIR}/{username}/{repo_name}'
        
        os.makedirs(full_path, exist_ok=True)
        
        filename = secure_filename(file.filename)
        file_path = os.path.join(full_path, filename)
        file.save(file_path)
        return True, filename
    
    @staticmethod
    def download_repo(username, repo_name):
        """Download do repositório como ZIP"""
        repo_path = f'{Config.REPOS_DIR}/{username}/{repo_name}'
        if not os.path.exists(repo_path):
            return None
        
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(repo_path):
                for file in files:
                    if '.cybergit' in root:
                        continue
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, repo_path)
                    zf.write(file_path, arcname)
        
        zip_buffer.seek(0)
        return zip_buffer
    
    @staticmethod
    def get_repo_size(username, repo_name):
        """Calcula o tamanho do repositório"""
        repo_path = f'{Config.REPOS_DIR}/{username}/{repo_name}'
        if not os.path.exists(repo_path):
            return 0
        
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(repo_path):
            if '.cybergit' in dirpath:
                continue
            for f in filenames:
                fp = os.path.join(dirpath, f)
                if os.path.exists(fp):
                    total_size += os.path.getsize(fp)
        
        return total_size

# ============================================
# FLASK APP
# ============================================
app = Flask(__name__)
app.config['SECRET_KEY'] = Config.SECRET_KEY
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024
CORS(app)

# ============================================
# DECORADORES
# ============================================
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login_page'))
        if not session.get('is_admin'):
            return "ACESSO NEGADO!", 403
        return f(*args, **kwargs)
    return decorated

# ============================================
# CSS PROFISSIONAL
# ============================================
STYLE = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;600;700&display=swap');
    @import url('https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css');
    
    :root {
        --bg: #0a0a12;
        --surface: #111122;
        --surface2: #181830;
        --border: #252545;
        --primary: #00d4ff;
        --primary-glow: rgba(0,212,255,0.3);
        --success: #00e676;
        --success-glow: rgba(0,230,118,0.3);
        --danger: #ff3355;
        --danger-glow: rgba(255,51,85,0.3);
        --warning: #ffaa00;
        --accent: #9944ff;
        --accent-glow: rgba(153,68,255,0.3);
        --text: #e8e8f5;
        --text2: #8888bb;
        --text3: #555588;
    }
    
    * { margin: 0; padding: 0; box-sizing: border-box; }
    
    body {
        font-family: 'Inter', sans-serif;
        background: var(--bg);
        color: var(--text);
        min-height: 100vh;
        background-image: 
            radial-gradient(ellipse at 15% 50%, rgba(0,212,255,0.03) 0%, transparent 55%),
            radial-gradient(ellipse at 85% 30%, rgba(153,68,255,0.03) 0%, transparent 55%),
            radial-gradient(ellipse at 50% 85%, rgba(0,230,118,0.03) 0%, transparent 55%);
        background-attachment: fixed;
    }
    
    .app { max-width: 1200px; margin: 0 auto; padding: 20px; }
    
    .header {
        text-align: center;
        padding: 40px 20px 30px;
        position: relative;
    }
    
    .header::before {
        content: '';
        position: absolute;
        top: 0; left: 50%; transform: translateX(-50%);
        width: 300px; height: 300px;
        background: radial-gradient(circle, rgba(0,212,255,0.06) 0%, transparent 70%);
        pointer-events: none;
    }
    
    .logo {
        font-family: 'Orbitron', sans-serif;
        font-size: 3em;
        font-weight: 900;
        letter-spacing: 4px;
        background: linear-gradient(135deg, #00d4ff, #9944ff, #00e676);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        position: relative;
        z-index: 1;
    }
    
    .subtitle {
        font-family: 'JetBrains Mono', monospace;
        color: var(--text3);
        letter-spacing: 3px;
        font-size: 0.85em;
        margin-top: 12px;
    }
    
    .nav {
        display: flex;
        gap: 8px;
        margin-bottom: 24px;
        flex-wrap: wrap;
        justify-content: center;
    }
    
    .nav a, .nav-link {
        padding: 12px 20px;
        border-radius: 10px;
        color: var(--text2);
        text-decoration: none;
        font-weight: 500;
        font-size: 0.9em;
        background: var(--surface);
        border: 1px solid transparent;
        transition: all 0.3s;
        display: inline-flex;
        align-items: center;
        gap: 8px;
    }
    
    .nav a:hover, .nav a.active, .nav-link:hover, .nav-link.active {
        color: var(--primary);
        border-color: var(--primary);
        background: rgba(0,212,255,0.05);
    }
    
    .card {
        background: var(--surface2);
        border: 1px solid var(--border);
        border-radius: 14px;
        padding: 24px;
        margin-bottom: 20px;
        box-shadow: 0 8px 32px rgba(0,0,0,0.3);
    }
    
    .card-title {
        font-size: 1.2em;
        font-weight: 700;
        color: var(--primary);
        margin-bottom: 16px;
        display: flex;
        align-items: center;
        gap: 10px;
    }
    
    .card-desc {
        color: var(--text2);
        font-size: 0.9em;
        margin-bottom: 16px;
    }
    
    .grid { display: grid; gap: 20px; }
    .grid-2 { grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); }
    .grid-3 { grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); }
    .grid-4 { grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); }
    
    .stat-card {
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 24px 20px;
        text-align: center;
        transition: all 0.3s;
    }
    
    .stat-card:hover {
        border-color: var(--primary);
        transform: translateY(-3px);
        box-shadow: 0 12px 40px var(--primary-glow);
    }
    
    .stat-value {
        font-family: 'Orbitron', sans-serif;
        font-size: 2.2em;
        font-weight: 900;
        background: linear-gradient(135deg, var(--primary), var(--accent));
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    
    .stat-label {
        color: var(--text2);
        font-size: 0.85em;
        margin-top: 8px;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    
    .form-group { margin-bottom: 16px; }
    
    .form-label {
        display: block;
        font-weight: 600;
        margin-bottom: 6px;
        color: var(--text2);
        font-size: 0.9em;
    }
    
    .form-input, input[type="text"], input[type="password"], input[type="email"], 
    input[type="url"], textarea, select {
        width: 100%;
        padding: 12px 16px;
        background: var(--bg);
        border: 2px solid var(--border);
        border-radius: 10px;
        color: var(--text);
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.9em;
        outline: none;
        transition: all 0.3s;
    }
    
    .form-input:focus, input:focus, textarea:focus, select:focus {
        border-color: var(--primary);
        box-shadow: 0 0 0 4px rgba(0,212,255,0.08);
    }
    
    textarea.form-input { min-height: 400px; resize: vertical; }
    
    .btn, button {
        padding: 12px 24px;
        border: none;
        border-radius: 10px;
        font-weight: 700;
        cursor: pointer;
        font-size: 0.9em;
        transition: all 0.3s;
        display: inline-flex;
        align-items: center;
        gap: 8px;
        text-decoration: none;
        font-family: 'Inter', sans-serif;
    }
    
    .btn-primary {
        background: linear-gradient(135deg, var(--success), #00c853);
        color: #000;
        box-shadow: 0 4px 20px var(--success-glow);
    }
    
    .btn-primary:hover { transform: translateY(-2px); box-shadow: 0 8px 30px var(--success-glow); }
    .btn-danger { background: linear-gradient(135deg, var(--danger), #c62828); color: #fff; }
    .btn-info { background: linear-gradient(135deg, var(--primary), #0099cc); color: #000; }
    .btn-warning { background: linear-gradient(135deg, var(--warning), #ff8800); color: #000; }
    .btn-outline { background: transparent; border: 2px solid var(--primary); color: var(--primary); }
    .btn-outline:hover { background: var(--primary); color: var(--bg); }
    .btn-sm { padding: 6px 14px; font-size: 0.8em; }
    .btn-block { width: 100%; justify-content: center; }
    .btn:hover { transform: translateY(-2px); opacity: 0.95; }
    
    table {
        width: 100%;
        border-collapse: collapse;
    }
    
    th, td {
        padding: 12px 14px;
        text-align: left;
        border-bottom: 1px solid var(--border);
    }
    
    th {
        background: rgba(0,212,255,0.03);
        color: var(--primary);
        font-size: 0.8em;
        text-transform: uppercase;
        letter-spacing: 1.5px;
        font-weight: 700;
    }
    
    tr:hover td { background: rgba(0,212,255,0.02); }
    
    .alert {
        padding: 14px 18px;
        border-radius: 10px;
        margin: 14px 0;
        font-weight: 500;
        display: flex;
        align-items: center;
        gap: 10px;
    }
    
    .alert-success { background: rgba(0,230,118,0.1); border: 1px solid rgba(0,230,118,0.3); color: var(--success); }
    .alert-error { background: rgba(255,51,85,0.1); border: 1px solid rgba(255,51,85,0.3); color: var(--danger); }
    .alert-info { background: rgba(0,212,255,0.1); border: 1px solid rgba(0,212,255,0.3); color: var(--primary); }
    .alert-warning { background: rgba(255,170,0,0.1); border: 1px solid rgba(255,170,0,0.3); color: var(--warning); }
    
    .badge {
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.75em;
        font-weight: 600;
        display: inline-block;
    }
    
    .badge-success { background: rgba(0,230,118,0.15); color: var(--success); }
    .badge-danger { background: rgba(255,51,85,0.15); color: var(--danger); }
    .badge-info { background: rgba(0,212,255,0.15); color: var(--primary); }
    .badge-warning { background: rgba(255,170,0,0.15); color: var(--warning); }
    .badge-purple { background: rgba(153,68,255,0.15); color: var(--accent); }
    
    .code-block {
        background: #000;
        border: 1px solid var(--border);
        border-radius: 10px;
        padding: 16px;
        font-family: 'JetBrains Mono', monospace;
        color: #00ff88;
        overflow-x: auto;
        white-space: pre-wrap;
        max-height: 500px;
        overflow-y: auto;
    }
    
    .file-list {
        border: 1px solid var(--border);
        border-radius: 10px;
        overflow: hidden;
    }
    
    .file-item {
        padding: 12px 16px;
        border-bottom: 1px solid var(--border);
        display: flex;
        align-items: center;
        gap: 12px;
        transition: all 0.2s;
        text-decoration: none;
        color: var(--text);
    }
    
    .file-item:hover { background: rgba(0,212,255,0.05); }
    .file-item:last-child { border-bottom: none; }
    .file-icon { color: var(--primary); width: 22px; text-align: center; font-size: 1.1em; }
    
    .breadcrumb {
        display: flex;
        gap: 6px;
        align-items: center;
        margin-bottom: 16px;
        flex-wrap: wrap;
    }
    
    .breadcrumb a {
        color: var(--primary);
        text-decoration: none;
    }
    
    .breadcrumb span { color: var(--text3); }
    
    .deploy-url {
        background: var(--bg);
        border: 1px solid var(--success);
        border-radius: 8px;
        padding: 10px 16px;
        display: flex;
        align-items: center;
        gap: 10px;
        font-family: 'JetBrains Mono', monospace;
    }
    
    .deploy-url code {
        color: var(--success);
        flex: 1;
    }
    
    .copy-btn {
        background: var(--success);
        color: #000;
        border: none;
        padding: 6px 12px;
        border-radius: 6px;
        cursor: pointer;
        font-weight: 700;
        font-size: 0.8em;
    }
    
    .footer {
        text-align: center;
        padding: 30px;
        color: var(--text3);
        font-size: 0.8em;
        margin-top: 40px;
    }
    
    @media (max-width: 768px) {
        .logo { font-size: 2em; }
        .card { padding: 16px; }
        .grid-2, .grid-3, .grid-4 { grid-template-columns: 1fr; }
        .stat-value { font-size: 1.8em; }
        .nav { gap: 4px; }
        .nav a { padding: 8px 14px; font-size: 0.8em; }
    }
</style>
"""

# ============================================
# PÁGINA HOME
# ============================================
@app.route('/')
def home():
    return render_template_string(f"""
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CyberHost - Hospedagem Web Profissional</title>
    {STYLE}
</head>
<body>
    <div class="app">
        <div class="header">
            <div class="logo">CYBERHOST</div>
            <div class="subtitle">HOSPEDAGEM WEB PROFISSIONAL</div>
        </div>
        
        <div class="nav">
            <a href="/" class="active"><i class="fas fa-home"></i> Home</a>
            <a href="/login"><i class="fas fa-sign-in-alt"></i> Login</a>
            <a href="/register"><i class="fas fa-user-plus"></i> Cadastro</a>
        </div>
        
        <div class="grid grid-2">
            <div class="card">
                <div class="card-title"><i class="fas fa-code"></i> Git Pobre</div>
                <p style="color:var(--text2);line-height:1.8;">
                    Sistema de versionamento integrado. Crie, edite e gerencie seus projetos diretamente no navegador.
                </p>
                <ul style="list-style:none;color:var(--text3);line-height:2.2;">
                    <li><i class="fas fa-check-circle" style="color:var(--success);"></i> Editor de código online</li>
                    <li><i class="fas fa-check-circle" style="color:var(--success);"></i> Upload de arquivos</li>
                    <li><i class="fas fa-check-circle" style="color:var(--success);"></i> Criação de pastas</li>
                    <li><i class="fas fa-check-circle" style="color:var(--success);"></i> Download ZIP</li>
                    <li><i class="fas fa-check-circle" style="color:var(--success);"></i> Histórico de alterações</li>
                </ul>
            </div>
            
            <div class="card">
                <div class="card-title"><i class="fas fa-rocket"></i> Deploy Automático</div>
                <p style="color:var(--text2);line-height:1.8;">
                    Hospede seus sites com um clique. Suporte a PHP, Python, JavaScript e HTML.
                </p>
                <ul style="list-style:none;color:var(--text3);line-height:2.2;">
                    <li><i class="fas fa-check-circle" style="color:var(--success);"></i> Subdomínio personalizado</li>
                    <li><i class="fas fa-check-circle" style="color:var(--success);"></i> Instalação automática de deps</li>
                    <li><i class="fas fa-check-circle" style="color:var(--success);"></i> HTTPS automático</li>
                    <li><i class="fas fa-check-circle" style="color:var(--success);"></i> Atualização instantânea</li>
                    <li><i class="fas fa-check-circle" style="color:var(--success);"></i> Logs de deploy</li>
                </ul>
            </div>
        </div>
        
        <div class="card" style="text-align:center;">
            <div class="card-title" style="justify-content:center;">
                <i class="fas fa-globe"></i> Tecnologias Suportadas
            </div>
            <div style="display:flex;gap:20px;justify-content:center;flex-wrap:wrap;margin-top:16px;">
                <span class="badge badge-info" style="font-size:1em;padding:10px 20px;">🐘 PHP</span>
                <span class="badge badge-warning" style="font-size:1em;padding:10px 20px;">🐍 Python</span>
                <span class="badge badge-success" style="font-size:1em;padding:10px 20px;">📜 JavaScript</span>
                <span class="badge badge-danger" style="font-size:1em;padding:10px 20px;">🌐 HTML/CSS</span>
            </div>
        </div>
        
        <a href="/register" class="btn btn-primary btn-block" style="margin-top:10px;padding:16px;">
            <i class="fas fa-rocket"></i> COMEÇAR AGORA - GRÁTIS
        </a>
        
        <div class="footer">
            © 2024 CyberHost v{Config.VERSION} | Desenvolvido por @cybersecofc
        </div>
    </div>
</body>
</html>
""")

# ============================================
# PÁGINA DE LOGIN
# ============================================
@app.route('/login', methods=['GET', 'POST'])
def login_page():
    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        if not username or not password:
            error = 'Preencha todos os campos!'
        else:
            success, result = db.authenticate(username, password)
            if success:
                session['username'] = username
                session['is_admin'] = result.get('is_admin', False)
                if result.get('is_admin'):
                    return redirect(url_for('admin_panel'))
                return redirect(url_for('dashboard'))
            else:
                error = result
    
    return render_template_string(f"""
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login - CyberHost</title>
    {STYLE}
</head>
<body>
    <div class="app" style="max-width:460px;margin-top:80px;">
        <div class="header">
            <div class="logo" style="font-size:2em;">CYBERHOST</div>
            <div class="subtitle">Login</div>
        </div>
        <div class="card">
            {f'<div class="alert alert-error"><i class="fas fa-exclamation-triangle"></i> {error}</div>' if error else ''}
            <form method="POST">
                <div class="form-group">
                    <label class="form-label"><i class="fas fa-user"></i> Usuário</label>
                    <input type="text" name="username" class="form-input" placeholder="Seu usuário" required>
                </div>
                <div class="form-group">
                    <label class="form-label"><i class="fas fa-lock"></i> Senha</label>
                    <input type="password" name="password" class="form-input" placeholder="Sua senha" required>
                </div>
                <button type="submit" class="btn btn-primary btn-block">
                    <i class="fas fa-sign-in-alt"></i> ENTRAR
                </button>
            </form>
            <p style="text-align:center;margin-top:16px;color:var(--text2);">
                Não tem conta? <a href="/register" style="color:var(--primary);">Cadastre-se</a>
            </p>
        </div>
    </div>
</body>
</html>
""")

# ============================================
# PÁGINA DE REGISTRO
# ============================================
@app.route('/register', methods=['GET', 'POST'])
def register_page():
    error = None
    success = None
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        email = request.form.get('email', '').strip()
        confirm = request.form.get('confirm_password', '')
        
        if not all([username, password, email]):
            error = 'Preencha todos os campos!'
        elif len(username) < 3:
            error = 'Usuário deve ter no mínimo 3 caracteres!'
        elif len(password) < 6:
            error = 'Senha deve ter no mínimo 6 caracteres!'
        elif password != confirm:
            error = 'Senhas não coincidem!'
        else:
            ok, msg = db.create_user(username, password, email)
            if ok:
                success = 'Conta criada com sucesso! Redirecionando...'
            else:
                error = msg
    
    return render_template_string(f"""
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Cadastro - CyberHost</title>
    {STYLE}
</head>
<body>
    <div class="app" style="max-width:460px;margin-top:60px;">
        <div class="header">
            <div class="logo" style="font-size:2em;">CYBERHOST</div>
            <div class="subtitle">Criar Conta</div>
        </div>
        <div class="card">
            {f'<div class="alert alert-error"><i class="fas fa-exclamation-triangle"></i> {error}</div>' if error else ''}
            {f'<div class="alert alert-success"><i class="fas fa-check-circle"></i> {success}</div>' if success else ''}
            <form method="POST">
                <div class="form-group">
                    <label class="form-label"><i class="fas fa-user"></i> Usuário</label>
                    <input type="text" name="username" class="form-input" placeholder="Escolha um usuário" required minlength="3">
                </div>
                <div class="form-group">
                    <label class="form-label"><i class="fas fa-envelope"></i> Email</label>
                    <input type="email" name="email" class="form-input" placeholder="seu@email.com" required>
                </div>
                <div class="form-group">
                    <label class="form-label"><i class="fas fa-lock"></i> Senha</label>
                    <input type="password" name="password" class="form-input" placeholder="Mínimo 6 caracteres" required minlength="6">
                </div>
                <div class="form-group">
                    <label class="form-label"><i class="fas fa-lock"></i> Confirmar Senha</label>
                    <input type="password" name="confirm_password" class="form-input" placeholder="Repita a senha" required>
                </div>
                <button type="submit" class="btn btn-primary btn-block">
                    <i class="fas fa-user-plus"></i> CRIAR CONTA
                </button>
            </form>
            <p style="text-align:center;margin-top:16px;color:var(--text2);">
                Já tem conta? <a href="/login" style="color:var(--primary);">Faça login</a>
            </p>
        </div>
    </div>
    {'<script>setTimeout(function(){window.location.href="/login";},2000);</script>' if success else ''}
</body>
</html>
""")

# ============================================
# DASHBOARD
# ============================================
@app.route('/dashboard')
@login_required
def dashboard():
    username = session['username']
    user = db.users.get(username, {})
    repos = db.get_user_repos(username)
    
    repos_html = ""
    for r in repos.values():
        deploy_status = r.get('deploy_status', 'not_deployed')
        status_badge = {
            'deployed': '<span class="badge badge-success">Online</span>',
            'not_deployed': '<span class="badge badge-warning">Não deployado</span>'
        }.get(deploy_status, '<span class="badge badge-warning">Pendente</span>')
        
        deploy_url = r.get('deploy_url', '')
        url_display = f'<a href="https://{deploy_url}" target="_blank" style="color:var(--success);font-size:0.8em;">{deploy_url}</a>' if deploy_url else '-'
        
        repos_html += f"""
        <tr>
            <td>
                <a href="/dashboard/repo/{r['id']}" style="color:var(--primary);text-decoration:none;font-weight:600;">
                    <i class="fas fa-folder"></i> {r['name']}
                </a>
            </td>
            <td>{r.get('description', '-')[:50]}</td>
            <td><span class="badge badge-info">{r.get('language', 'html')}</span></td>
            <td>{status_badge}</td>
            <td style="font-size:0.8em;color:var(--text3);">{r.get('updated_at', '')[:10]}</td>
            <td>
                <a href="/dashboard/repo/{r['id']}" class="btn btn-info btn-sm"><i class="fas fa-eye"></i></a>
                <a href="/dashboard/repo/{r['id']}/download" class="btn btn-outline btn-sm"><i class="fas fa-download"></i></a>
                <a href="/dashboard/repo/{r['id']}/delete" class="btn btn-danger btn-sm" onclick="return confirm('Tem certeza?')"><i class="fas fa-trash"></i></a>
            </td>
        </tr>"""
    
    return render_template_string(f"""
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dashboard - CyberHost</title>
    {STYLE}
</head>
<body>
    <div class="app">
        <div class="header">
            <div class="logo" style="font-size:2em;">DASHBOARD</div>
            <div class="subtitle">Bem-vindo, {username}!</div>
        </div>
        
        <div class="nav">
            <a href="/dashboard" class="active"><i class="fas fa-tachometer-alt"></i> Visão Geral</a>
            <a href="/dashboard/new-repo"><i class="fas fa-plus-circle"></i> Novo Repositório</a>
            <a href="/dashboard/repos"><i class="fas fa-code-branch"></i> Meus Repos</a>
            <a href="/logout" style="color:var(--danger);"><i class="fas fa-sign-out-alt"></i> Sair</a>
        </div>
        
        <div class="grid grid-3" style="margin-bottom:24px;">
            <div class="stat-card">
                <div class="stat-value">{len(repos)}</div>
                <div class="stat-label">Repositórios</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{user.get('deploys_count', 0)}</div>
                <div class="stat-label">Deploys</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{user.get('plan', 'free').upper()}</div>
                <div class="stat-label">Plano</div>
            </div>
        </div>
        
        <div class="card">
            <div class="card-title">
                <i class="fas fa-list"></i> Meus Repositórios ({len(repos)})
                <a href="/dashboard/new-repo" class="btn btn-primary btn-sm" style="margin-left:auto;">
                    <i class="fas fa-plus"></i> Novo
                </a>
            </div>
            
            {f'''<div style="overflow-x:auto;">
                <table>
                    <thead><tr><th>Nome</th><th>Descrição</th><th>Tipo</th><th>Status</th><th>Atualizado</th><th>Ações</th></tr></thead>
                    <tbody>{repos_html}</tbody>
                </table>
            </div>''' if repos else '<p style="text-align:center;color:var(--text3);padding:30px;">Nenhum repositório ainda. <a href="/dashboard/new-repo" style="color:var(--primary);">Criar primeiro repo</a></p>'}
        </div>
    </div>
</body>
</html>
""")

# ============================================
# NOVO REPOSITÓRIO
# ============================================
@app.route('/dashboard/new-repo', methods=['GET', 'POST'])
@login_required
def new_repo():
    username = session['username']
    error = None
    
    if request.method == 'POST':
        repo_name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        language = request.form.get('language', 'html')
        
        if not repo_name:
            error = 'Nome do repositório é obrigatório!'
        elif not regex.match(r'^[a-zA-Z0-9_-]+$', repo_name):
            error = 'Nome inválido! Use apenas letras, números, - e _'
        else:
            ok, result = db.create_repo(username, repo_name, description, language)
            if ok:
                return redirect(url_for('repo_view', repo_id=result))
            else:
                error = result
    
    return render_template_string(f"""
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <title>Novo Repositório - CyberHost</title>
    {STYLE}
</head>
<body>
    <div class="app" style="max-width:600px;margin-top:60px;">
        <div class="card">
            <div class="card-title"><i class="fas fa-plus-circle"></i> Novo Repositório</div>
            {f'<div class="alert alert-error">{error}</div>' if error else ''}
            <form method="POST">
                <div class="form-group">
                    <label class="form-label">📁 Nome do Repositório</label>
                    <input type="text" name="name" class="form-input" placeholder="meu-projeto" required>
                </div>
                <div class="form-group">
                    <label class="form-label">📝 Descrição</label>
                    <textarea name="description" class="form-input" style="min-height:80px;" placeholder="Descrição do projeto..."></textarea>
                </div>
                <div class="form-group">
                    <label class="form-label">🔧 Tipo de Projeto</label>
                    <select name="language" class="form-input">
                        <option value="html">🌐 HTML</option>
                        <option value="python">🐍 Python</option>
                        <option value="php">🐘 PHP</option>
                        <option value="javascript">📜 JavaScript</option>
                    </select>
                </div>
                <button type="submit" class="btn btn-primary btn-block">CRIAR REPOSITÓRIO</button>
            </form>
        </div>
    </div>
</body>
</html>
""")

# ============================================
# VISUALIZAR REPOSITÓRIO
# ============================================
@app.route('/dashboard/repo/<repo_id>')
@login_required
def repo_view(repo_id):
    username = session['username']
    repo = db.repos.get(repo_id)
    
    if not repo or repo['owner'] != username:
        return "Repositório não encontrado!", 404
    
    files = GitPobre.get_files(username, repo['name'])
    total_size = GitPobre.get_repo_size(username, repo['name'])
    
    files_html = ""
    for f in files:
        icon = 'fa-folder' if f['type'] == 'folder' else 'fa-file-code'
        click_url = f"/dashboard/repo/{repo_id}/file?path={f['path']}" if f['type'] == 'file' else f"/dashboard/repo/{repo_id}?path={f['path']}"
        
        files_html += f"""
        <div class="file-item" style="cursor:pointer;" onclick="location.href='{click_url}'">
            <i class="fas {icon} file-icon"></i>
            <span style="flex:1;">{f['name']}</span>
            <span style="color:var(--text3);font-size:0.8em;">{f.get('size', 0)} bytes</span>
            <span style="color:var(--text3);font-size:0.75em;">{f.get('modified', '')}</span>
            <a href="/dashboard/repo/{repo_id}/delete-file?path={f['path']}" class="btn btn-danger btn-sm" onclick="event.stopPropagation();return confirm('Deletar?')">
                <i class="fas fa-trash"></i>
            </a>
        </div>"""
    
    deploy_status_html = ""
    if repo.get('deploy_url'):
        deploy_status_html = f"""
        <div class="alert alert-success">
            <i class="fas fa-globe"></i> Site online: 
            <a href="https://{repo['deploy_url']}" target="_blank" style="color:var(--primary);">{repo['deploy_url']}</a>
        </div>"""
    
    return render_template_string(f"""
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <title>{repo['name']} - CyberHost</title>
    {STYLE}
</head>
<body>
    <div class="app">
        <div style="display:flex;align-items:center;gap:16px;margin-bottom:20px;flex-wrap:wrap;">
            <a href="/dashboard" style="color:var(--text2);"><i class="fas fa-arrow-left"></i></a>
            <div style="flex:1;">
                <h2 style="color:var(--primary);">{repo['name']}</h2>
                <p style="color:var(--text3);font-size:0.85em;">{repo.get('description', '')} | {total_size} bytes | {len(files)} arquivos</p>
            </div>
        </div>
        
        {deploy_status_html}
        
        <div class="nav">
            <a href="/dashboard/repo/{repo_id}" class="active"><i class="fas fa-code"></i> Arquivos</a>
            <a href="/dashboard/repo/{repo_id}/editor"><i class="fas fa-edit"></i> Novo Arquivo</a>
            <a href="/dashboard/repo/{repo_id}/new-folder"><i class="fas fa-folder-plus"></i> Nova Pasta</a>
            <a href="/dashboard/repo/{repo_id}/upload"><i class="fas fa-upload"></i> Upload</a>
            <a href="/dashboard/repo/{repo_id}/deploy"><i class="fas fa-rocket"></i> Deploy</a>
            <a href="/dashboard/repo/{repo_id}/download"><i class="fas fa-download"></i> Download ZIP</a>
            <a href="/dashboard/repo/{repo_id}/delete" style="color:var(--danger);" onclick="return confirm('Tem certeza?')"><i class="fas fa-trash"></i> Deletar</a>
        </div>
        
        <div class="card">
            <div class="card-title"><i class="fas fa-folder-tree"></i> Arquivos</div>
            <div class="file-list">
                {files_html if files else '<div class="file-item"><span style="color:var(--text3);">Repositório vazio</span></div>'}
            </div>
        </div>
    </div>
</body>
</html>
""")

# ============================================
# EDITOR DE ARQUIVO
# ============================================
@app.route('/dashboard/repo/<repo_id>/editor', methods=['GET', 'POST'])
@login_required
def repo_editor(repo_id):
    username = session['username']
    repo = db.repos.get(repo_id)
    
    if not repo or repo['owner'] != username:
        return "Repositório não encontrado!", 404
    
    file_path = request.args.get('path', '')
    content = ''
    success = None
    error = None
    
    if file_path:
        content = GitPobre.get_file_content(username, repo['name'], file_path) or ''
    
    if request.method == 'POST':
        file_path = request.form.get('path', '').strip()
        content = request.form.get('content', '')
        
        if not file_path:
            error = 'Caminho do arquivo é obrigatório!'
        else:
            ok, msg = GitPobre.save_file(username, repo['name'], file_path, content)
            if ok:
                success = msg
            else:
                error = msg
    
    return render_template_string(f"""
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <title>Editor - {repo['name']}</title>
    {STYLE}
</head>
<body>
    <div class="app">
        <div style="margin-bottom:16px;">
            <a href="/dashboard/repo/{repo_id}" style="color:var(--text2);"><i class="fas fa-arrow-left"></i> Voltar</a>
        </div>
        
        {f'<div class="alert alert-success">{success}</div>' if success else ''}
        {f'<div class="alert alert-error">{error}</div>' if error else ''}
        
        <div class="card">
            <div class="card-title"><i class="fas fa-edit"></i> {'Editar' if file_path else 'Novo'} Arquivo</div>
            <form method="POST">
                <div class="form-group">
                    <label class="form-label">📄 Caminho do Arquivo</label>
                    <input type="text" name="path" class="form-input" value="{file_path}" placeholder="index.html">
                </div>
                <div class="form-group">
                    <label class="form-label">📝 Conteúdo</label>
                    <textarea name="content" class="form-input">{content}</textarea>
                </div>
                <div style="display:flex;gap:10px;">
                    <button type="submit" class="btn btn-primary"><i class="fas fa-save"></i> SALVAR</button>
                    <a href="/dashboard/repo/{repo_id}" class="btn btn-outline">Cancelar</a>
                </div>
            </form>
        </div>
    </div>
</body>
</html>
""")

# ============================================
# UPLOAD DE ARQUIVO
# ============================================
@app.route('/dashboard/repo/<repo_id>/upload', methods=['GET', 'POST'])
@login_required
def repo_upload(repo_id):
    username = session['username']
    repo = db.repos.get(repo_id)
    
    if not repo or repo['owner'] != username:
        return "Repositório não encontrado!", 404
    
    success = None
    error = None
    
    if request.method == 'POST':
        if 'file' not in request.files:
            error = 'Nenhum arquivo enviado!'
        else:
            file = request.files['file']
            if file.filename:
                ok, filename = GitPobre.upload_file(username, repo['name'], file)
                if ok:
                    success = f'Arquivo {filename} enviado com sucesso!'
                else:
                    error = 'Erro ao enviar arquivo!'
    
    return render_template_string(f"""
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <title>Upload - {repo['name']}</title>
    {STYLE}
</head>
<body>
    <div class="app" style="max-width:600px;margin-top:60px;">
        <div style="margin-bottom:16px;">
            <a href="/dashboard/repo/{repo_id}" style="color:var(--text2);"><i class="fas fa-arrow-left"></i> Voltar</a>
        </div>
        
        {f'<div class="alert alert-success">{success}</div>' if success else ''}
        {f'<div class="alert alert-error">{error}</div>' if error else ''}
        
        <div class="card">
            <div class="card-title"><i class="fas fa-upload"></i> Upload de Arquivo</div>
            <form method="POST" enctype="multipart/form-data">
                <div class="form-group">
                    <label class="form-label">📁 Selecione o arquivo</label>
                    <input type="file" name="file" class="form-input" required>
                </div>
                <button type="submit" class="btn btn-primary btn-block">ENVIAR ARQUIVO</button>
            </form>
        </div>
    </div>
</body>
</html>
""")

# ============================================
# DEPLOY
# ============================================
@app.route('/dashboard/repo/<repo_id>/deploy', methods=['GET', 'POST'])
@login_required
def repo_deploy(repo_id):
    username = session['username']
    repo = db.repos.get(repo_id)
    
    if not repo or repo['owner'] != username:
        return "Repositório não encontrado!", 404
    
    success = None
    error = None
    
    if request.method == 'POST':
        subdomain = request.form.get('subdomain', '').strip()
        ok, result = db.deploy_repo(repo_id, username, subdomain)
        if ok:
            success = f'Deploy realizado! URL: https://{result}'
        else:
            error = result
    
    return render_template_string(f"""
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <title>Deploy - {repo['name']}</title>
    {STYLE}
</head>
<body>
    <div class="app" style="max-width:600px;margin-top:60px;">
        <div style="margin-bottom:16px;">
            <a href="/dashboard/repo/{repo_id}" style="color:var(--text2);"><i class="fas fa-arrow-left"></i> Voltar</a>
        </div>
        
        {f'<div class="alert alert-success">{success}</div>' if success else ''}
        {f'<div class="alert alert-error">{error}</div>' if error else ''}
        
        {f'''<div class="alert alert-info">
            <i class="fas fa-globe"></i> Site atual: 
            <a href="https://{repo["deploy_url"]}" target="_blank" style="color:var(--primary);">{repo["deploy_url"]}</a>
        </div>''' if repo.get('deploy_url') else ''}
        
        <div class="card">
            <div class="card-title"><i class="fas fa-rocket"></i> Fazer Deploy</div>
            <p style="color:var(--text2);margin-bottom:20px;">
                Seu site ficará disponível em: <br>
                <code style="background:var(--bg);padding:4px 8px;border-radius:4px;display:inline-block;margin-top:8px;">cyber-SEUNOME.onrender.com</code>
            </p>
            <form method="POST">
                <div class="form-group">
                    <label class="form-label">🌐 Subdomínio (opcional)</label>
                    <input type="text" name="subdomain" class="form-input" placeholder="meu-app">
                </div>
                <button type="submit" class="btn btn-primary btn-block"><i class="fas fa-rocket"></i> FAZER DEPLOY</button>
            </form>
        </div>
    </div>
</body>
</html>
""")

# ============================================
# DOWNLOAD DO REPO
# ============================================
@app.route('/dashboard/repo/<repo_id>/download')
@login_required
def repo_download(repo_id):
    username = session['username']
    repo = db.repos.get(repo_id)
    
    if not repo or repo['owner'] != username:
        return "Repositório não encontrado!", 404
    
    zip_buffer = GitPobre.download_repo(username, repo['name'])
    if not zip_buffer:
        return "Erro ao criar ZIP!", 500
    
    return send_file(
        zip_buffer,
        mimetype='application/zip',
        as_attachment=True,
        download_name=f'{repo["name"]}.zip'
    )

# ============================================
# DELETAR ARQUIVO
# ============================================
@app.route('/dashboard/repo/<repo_id>/delete-file')
@login_required
def repo_delete_file(repo_id):
    username = session['username']
    repo = db.repos.get(repo_id)
    
    if not repo or repo['owner'] != username:
        return "Repositório não encontrado!", 404
    
    file_path = request.args.get('path', '')
    GitPobre.delete_file(username, repo['name'], file_path)
    return redirect(url_for('repo_view', repo_id=repo_id))

# ============================================
# NOVA PASTA
# ============================================
@app.route('/dashboard/repo/<repo_id>/new-folder', methods=['GET', 'POST'])
@login_required
def repo_new_folder(repo_id):
    username = session['username']
    repo = db.repos.get(repo_id)
    
    if not repo or repo['owner'] != username:
        return "Repositório não encontrado!", 404
    
    if request.method == 'POST':
        folder_name = request.form.get('folder_name', '').strip()
        if folder_name:
            GitPobre.create_folder(username, repo['name'], folder_name)
        return redirect(url_for('repo_view', repo_id=repo_id))
    
    return render_template_string(f"""
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <title>Nova Pasta - {repo['name']}</title>
    {STYLE}
</head>
<body>
    <div class="app" style="max-width:500px;margin-top:60px;">
        <div class="card">
            <div class="card-title"><i class="fas fa-folder-plus"></i> Nova Pasta</div>
            <form method="POST">
                <div class="form-group">
                    <label class="form-label">📁 Nome da Pasta</label>
                    <input type="text" name="folder_name" class="form-input" placeholder="minha-pasta" required>
                </div>
                <button type="submit" class="btn btn-primary btn-block">CRIAR PASTA</button>
            </form>
        </div>
    </div>
</body>
</html>
""")

# ============================================
# DELETAR REPOSITÓRIO
# ============================================
@app.route('/dashboard/repo/<repo_id>/delete')
@login_required
def repo_delete(repo_id):
    username = session['username']
    db.delete_repo(repo_id, username)
    return redirect(url_for('dashboard'))

# ============================================
# PAINEL ADMIN
# ============================================
@app.route('/admin')
@admin_required
def admin_panel():
    users_list = []
    for uname, udata in db.users.items():
        repos_count = len([r for r in db.repos.values() if r['owner'] == uname])
        users_list.append({
            'username': uname,
            'is_admin': udata.get('is_admin', False),
            'blocked': udata.get('blocked', False),
            'email': udata.get('email', ''),
            'created_at': udata.get('created_at', '')[:10],
            'repos_count': repos_count
        })
    
    repos_list = [{
        'id': r['id'],
        'name': r['name'],
        'owner': r['owner'],
        'language': r.get('language', 'html'),
        'deploy_url': r.get('deploy_url', ''),
        'created_at': r.get('created_at', '')[:10]
    } for r in db.repos.values()]
    
    users_rows = ""
    for u in users_list:
        if u['is_admin']:
            actions = '<span class="badge badge-purple">Admin</span>'
        else:
            actions = f'<a href="/admin/block/{u["username"]}" class="btn btn-warning btn-sm">Bloquear</a> '
            actions += f'<a href="/admin/delete/{u["username"]}" class="btn btn-danger btn-sm" onclick="return confirm(\'Tem certeza?\')">Remover</a>'
        
        users_rows += f"""
        <tr>
            <td><strong>{u['username']}</strong>{' 👑' if u['is_admin'] else ''}</td>
            <td>{u['email']}</td>
            <td>{u['repos_count']}</td>
            <td><span class="badge {'badge-danger' if u['blocked'] else 'badge-success'}">{'Bloqueado' if u['blocked'] else 'Ativo'}</span></td>
            <td>{u['created_at']}</td>
            <td>{actions}</td>
        </tr>"""
    
    repos_rows = ""
    for r in repos_list:
        repos_rows += f"""
        <tr>
            <td><strong>{r['name']}</strong></td>
            <td>{r['owner']}</td>
            <td><span class="badge badge-info">{r['language']}</span></td>
            <td>{'<a href="https://'+r['deploy_url']+'" target="_blank" style="color:var(--success);">'+r['deploy_url']+'</a>' if r['deploy_url'] else '-'}</td>
            <td>{r['created_at']}</td>
        </tr>"""
    
    return render_template_string(f"""
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <title>Painel Admin - CyberHost</title>
    {STYLE}
</head>
<body>
    <div class="app">
        <div class="header">
            <div class="logo" style="font-size:2em;">PAINEL ADMIN</div>
        </div>
        
        <div class="nav">
            <a href="/admin" class="active"><i class="fas fa-shield-halved"></i> Admin</a>
            <a href="/dashboard"><i class="fas fa-tachometer-alt"></i> Dashboard</a>
            <a href="/logout" style="color:var(--danger);"><i class="fas fa-sign-out-alt"></i> Sair</a>
        </div>
        
        <div class="grid grid-3" style="margin-bottom:24px;">
            <div class="stat-card">
                <div class="stat-value">{len(db.users)}</div>
                <div class="stat-label">Usuários</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{len(db.repos)}</div>
                <div class="stat-label">Repositórios</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{len(db.deploys)}</div>
                <div class="stat-label">Deploys</div>
            </div>
        </div>
        
        <div class="card">
            <div class="card-title"><i class="fas fa-users"></i> Usuários</div>
            <div style="overflow-x:auto;">
                <table>
                    <thead><tr><th>Usuário</th><th>Email</th><th>Repos</th><th>Status</th><th>Data</th><th>Ações</th></tr></thead>
                    <tbody>{users_rows}</tbody>
                </table>
            </div>
        </div>
        
        <div class="card">
            <div class="card-title"><i class="fas fa-code-branch"></i> Repositórios</div>
            <div style="overflow-x:auto;">
                <table>
                    <thead><tr><th>Nome</th><th>Dono</th><th>Tipo</th><th>Deploy</th><th>Data</th></tr></thead>
                    <tbody>{repos_rows}</tbody>
                </table>
            </div>
        </div>
    </div>
</body>
</html>
""")

@app.route('/admin/block/<username>')
@admin_required
def admin_block(username):
    if username in db.users:
        db.users[username]['blocked'] = True
        db._save(Config.USERS_FILE, db.users)
    return redirect(url_for('admin_panel'))

@app.route('/admin/delete/<username>')
@admin_required
def admin_delete(username):
    if username != Config.ADMIN_USER and username in db.users:
        # Remover repositórios do usuário
        for repo_id in list(db.repos.keys()):
            if db.repos[repo_id]['owner'] == username:
                db.delete_repo(repo_id, username)
        del db.users[username]
        db._save(Config.USERS_FILE, db.users)
    return redirect(url_for('admin_panel'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

@app.route('/ping')
def ping():
    return jsonify({'status': 'online', 'version': Config.VERSION})

# ============================================
# AUTO-PING
# ============================================
def keep_alive():
    while True:
        try:
            http_requests.get(f"{Config.BASE_URL}/ping", timeout=10)
        except:
            pass
        time.sleep(240)

# ============================================
# INICIAR
# ============================================
if __name__ == '__main__':
    threading.Thread(target=keep_alive, daemon=True).start()
    
    print(f"""
{Fore.CYAN}╔══════════════════════════════════════════╗
║   {Fore.YELLOW}⚡ CYBERHOST v{Config.VERSION} - ONLINE{Fore.CYAN}            ║
║   {Fore.WHITE}🌐 http://localhost:{Config.PORT}{Fore.CYAN}              ║
║   {Fore.WHITE}👑 admin: cyber / cybersecofcadm{Fore.CYAN}     ║
║   {Fore.GREEN}✅ Git Pobre{Fore.CYAN}                              ║
║   {Fore.GREEN}✅ Deploy Automático{Fore.CYAN}                      ║
║   {Fore.GREEN}✅ PHP • Python • JS • HTML{Fore.CYAN}              ║
╚══════════════════════════════════════════╝{Style.RESET_ALL}
    """)
    
    app.run(host='0.0.0.0', port=Config.PORT, debug=False, threaded=True)
