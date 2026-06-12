"""
⚡ CYBERHOST v1.0 - HOSPEDAGEM WEB COMPLETA
Sistema de Hospedagem com Git Pobre Integrado
Multi-Usuário | Deploy Automático | Painel Admin
By @cybersecofc
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
import re as regex
from datetime import datetime
from pathlib import Path
from functools import wraps
from typing import Dict, List, Any, Optional
from werkzeug.utils import secure_filename

# Instalação automática
def install_package(package):
    try:
        __import__(package.replace('-', '_'))
    except ImportError:
        print(f"[INSTALANDO] {package}...")
        os.system(f"{sys.executable} -m pip install {package} --quiet --no-warn-script-location")
        print(f"[OK] {package}")

print("=" * 60)
print("⚡ CYBERHOST v1.0 - INICIANDO")
print("=" * 60)

DEPS = ['flask', 'flask-cors', 'werkzeug', 'requests', 'gitpython', 'colorama']
for dep in DEPS:
    install_package(dep)

from flask import (Flask, render_template_string, jsonify, request, 
                   redirect, url_for, session, send_file, send_from_directory)
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import requests as http_requests
from colorama import init, Fore, Style
import git

init(autoreset=True)

# ============================================
# CONFIGURAÇÕES
# ============================================
class Config:
    SECRET_KEY = secrets.token_hex(32)
    PORT = int(os.environ.get('PORT', 5000))
    BASE_URL = os.environ.get('RENDER_EXTERNAL_URL', f'http://localhost:{PORT}')
    ADMIN_USER = "cyber"
    ADMIN_PASS = "cybersecofcadm"
    
    # Diretórios
    DATA_DIR = 'cyberhost_data'
    USERS_DIR = f'{DATA_DIR}/users'
    REPOS_DIR = f'{DATA_DIR}/repos'
    DEPLOYS_DIR = f'{DATA_DIR}/deploys'
    SITES_DIR = f'{DATA_DIR}/sites'
    
    # Arquivos
    USERS_FILE = f'{DATA_DIR}/users.json'
    REPOS_FILE = f'{DATA_DIR}/repos.json'
    DEPLOYS_FILE = f'{DATA_DIR}/deploys.json'
    
    # Domínios permitidos
    ALLOWED_EXTENSIONS = {'php', 'js', 'py', 'html', 'css', 'json', 'txt', 'md', 'xml', 'htaccess'}

# Criar diretórios
for d in [Config.DATA_DIR, Config.USERS_DIR, Config.REPOS_DIR, Config.DEPLOYS_DIR, Config.SITES_DIR]:
    os.makedirs(d, exist_ok=True)

# ============================================
# BANCO DE DADOS
# ============================================
class Database:
    def __init__(self):
        self.users = self._load(Config.USERS_FILE)
        self.repos = self._load(Config.REPOS_FILE)
        self.deploys = self._load(Config.DEPLOYS_FILE)
        self._init_admin()
    
    def _load(self, filename):
        if os.path.exists(filename):
            with open(filename, 'r') as f:
                return json.load(f)
        return {}
    
    def _save(self, filename, data):
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def _init_admin(self):
        if Config.ADMIN_USER not in self.users:
            self.users[Config.ADMIN_USER] = {
                'password': generate_password_hash(Config.ADMIN_PASS),
                'is_admin': True,
                'created_at': datetime.now().isoformat(),
                'email': 'admin@cyberhost.com',
                'plan': 'admin',
                'blocked': False
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
        
        # Criar diretórios do usuário
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
    
    def create_repo(self, username, repo_name, description=""):
        repo_id = uuid.uuid4().hex[:12]
        repo_path = f'{Config.REPOS_DIR}/{username}/{repo_name}'
        
        if repo_id in self.repos:
            return False, "Repositório já existe!"
        
        # Criar diretório e inicializar Git
        os.makedirs(repo_path, exist_ok=True)
        
        try:
            repo = git.Repo.init(repo_path)
            # Criar README inicial
            readme_path = f'{repo_path}/README.md'
            with open(readme_path, 'w') as f:
                f.write(f'# {repo_name}\n\n{description}\n\nCriado com CyberHost')
            repo.index.add(['README.md'])
            repo.index.commit('Initial commit')
        except:
            pass
        
        self.repos[repo_id] = {
            'id': repo_id,
            'owner': username,
            'name': repo_name,
            'description': description,
            'path': repo_path,
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat(),
            'files_count': 1,
            'is_public': True,
            'language': 'markdown',
            'deploy_url': None
        }
        
        self.users[username]['repos_count'] = self.users[username].get('repos_count', 0) + 1
        self._save(Config.REPOS_FILE, self.repos)
        self._save(Config.USERS_FILE, self.users)
        
        return True, repo_id
    
    def delete_repo(self, repo_id, username):
        repo = self.repos.get(repo_id)
        if not repo or repo['owner'] != username:
            return False
        
        # Remover arquivos
        repo_path = repo['path']
        if os.path.exists(repo_path):
            shutil.rmtree(repo_path, ignore_errors=True)
        
        # Remover deploy se existir
        if repo.get('deploy_url'):
            deploy_path = f'{Config.DEPLOYS_DIR}/{username}/{repo["name"]}'
            if os.path.exists(deploy_path):
                shutil.rmtree(deploy_path, ignore_errors=True)
        
        del self.repos[repo_id]
        self.users[username]['repos_count'] = max(0, self.users[username].get('repos_count', 1) - 1)
        self._save(Config.REPOS_FILE, self.repos)
        self._save(Config.USERS_FILE, self.users)
        return True
    
    def deploy_repo(self, repo_id, username, subdomain):
        repo = self.repos.get(repo_id)
        if not repo or repo['owner'] != username:
            return False, "Repositório não encontrado!"
        
        # Validar subdomínio
        subdomain = regex.sub(r'[^a-z0-9-]', '', subdomain.lower())
        if not subdomain:
            subdomain = f"{username}-{repo['name']}"
        
        deploy_url = f"cyber-{subdomain}.onrender.com"
        deploy_path = f'{Config.DEPLOYS_DIR}/{username}/{repo["name"]}'
        
        # Copiar arquivos do repo para deploy
        repo_path = repo['path']
        if os.path.exists(deploy_path):
            shutil.rmtree(deploy_path)
        
        shutil.copytree(repo_path, deploy_path)
        
        # Instalar dependências se houver requirements.txt
        requirements = f'{deploy_path}/requirements.txt'
        if os.path.exists(requirements):
            try:
                subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', requirements, '--target', deploy_path],
                             capture_output=True, timeout=60)
            except:
                pass
        
        repo['deploy_url'] = deploy_url
        repo['updated_at'] = datetime.now().isoformat()
        
        self.users[username]['deploys_count'] = self.users[username].get('deploys_count', 0) + 1
        self._save(Config.REPOS_FILE, self.repos)
        self._save(Config.USERS_FILE, self.users)
        
        return True, deploy_url
    
    def get_user_repos(self, username):
        return {k: v for k, v in self.repos.items() if v['owner'] == username}
    
    def get_all_repos(self):
        return self.repos

db = Database()

# ============================================
# GIT POBRE - CONTROLE DE VERSÃO
# ============================================
class GitPobre:
    """Sistema Git Pobre - Controle de versão simplificado"""
    
    @staticmethod
    def init_repo(username, repo_name):
        """Inicializa um repositório Git Pobre"""
        repo_path = f'{Config.REPOS_DIR}/{username}/{repo_name}'
        os.makedirs(repo_path, exist_ok=True)
        
        try:
            repo = git.Repo.init(repo_path)
            return True, repo
        except Exception as e:
            return False, str(e)
    
    @staticmethod
    def get_files(username, repo_name, path=""):
        """Lista arquivos do repositório"""
        repo_path = f'{Config.REPOS_DIR}/{username}/{repo_name}/{path}'
        if not os.path.exists(repo_path):
            return []
        
        files = []
        for item in os.listdir(repo_path):
            item_path = os.path.join(repo_path, item)
            rel_path = os.path.join(path, item) if path else item
            
            if os.path.isfile(item_path):
                files.append({
                    'name': item,
                    'path': rel_path,
                    'type': 'file',
                    'size': os.path.getsize(item_path),
                    'extension': item.split('.')[-1] if '.' in item else '',
                    'modified': datetime.fromtimestamp(os.path.getmtime(item_path)).isoformat()
                })
            else:
                files.append({
                    'name': item,
                    'path': rel_path,
                    'type': 'folder',
                    'size': 0
                })
        
        return sorted(files, key=lambda x: (x['type'] != 'folder', x['name'].lower()))
    
    @staticmethod
    def get_file_content(username, repo_name, file_path):
        """Lê conteúdo de um arquivo"""
        full_path = f'{Config.REPOS_DIR}/{username}/{repo_name}/{file_path}'
        if not os.path.exists(full_path):
            return None
        
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                return f.read()
        except:
            with open(full_path, 'r', encoding='latin-1') as f:
                return f.read()
    
    @staticmethod
    def save_file(username, repo_name, file_path, content):
        """Salva ou atualiza um arquivo"""
        full_path = f'{Config.REPOS_DIR}/{username}/{repo_name}/{file_path}'
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        
        try:
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # Commit automático no Git
            try:
                repo = git.Repo(f'{Config.REPOS_DIR}/{username}/{repo_name}')
                repo.index.add([file_path])
                repo.index.commit(f'Update {file_path}')
            except:
                pass
            
            return True
        except Exception as e:
            return False
    
    @staticmethod
    def delete_file(username, repo_name, file_path):
        """Deleta um arquivo"""
        full_path = f'{Config.REPOS_DIR}/{username}/{repo_name}/{file_path}'
        if os.path.exists(full_path):
            if os.path.isfile(full_path):
                os.remove(full_path)
            else:
                shutil.rmtree(full_path)
            
            try:
                repo = git.Repo(f'{Config.REPOS_DIR}/{username}/{repo_name}')
                repo.index.remove([file_path], working_tree=True)
                repo.index.commit(f'Delete {file_path}')
            except:
                pass
            
            return True
        return False
    
    @staticmethod
    def upload_file(username, repo_name, file, path=""):
        """Upload de arquivo"""
        if path:
            full_path = f'{Config.REPOS_DIR}/{username}/{repo_name}/{path}'
        else:
            full_path = f'{Config.REPOS_DIR}/{username}/{repo_name}'
        
        os.makedirs(full_path, exist_ok=True)
        
        filename = secure_filename(file.filename)
        file.save(os.path.join(full_path, filename))
        
        # Commit automático
        try:
            repo = git.Repo(f'{Config.REPOS_DIR}/{username}/{repo_name}')
            rel_path = os.path.join(path, filename) if path else filename
            repo.index.add([rel_path])
            repo.index.commit(f'Upload {filename}')
        except:
            pass
        
        return True

# ============================================
# FLASK APP
# ============================================
app = Flask(__name__)
app.config['SECRET_KEY'] = Config.SECRET_KEY
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB
CORS(app)

# Decoradores
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
# CSS GLOBAL
# ============================================
STYLE = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;700&display=swap');
    @import url('https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css');
    
    :root {
        --bg: #0a0a14;
        --surface: #0f0f20;
        --surface2: #141428;
        --border: #1f1f40;
        --primary: #00d4ff;
        --success: #00e676;
        --danger: #ff3355;
        --warning: #ffaa00;
        --accent: #9944ff;
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
    }
    
    .app { max-width: 1200px; margin: 0 auto; padding: 20px; }
    
    .header {
        text-align: center;
        padding: 30px 20px;
    }
    
    .logo {
        font-family: 'Orbitron', sans-serif;
        font-size: 2.5em;
        font-weight: 900;
        background: linear-gradient(135deg, #00d4ff, #9944ff);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    
    .subtitle {
        font-family: 'JetBrains Mono', monospace;
        color: var(--text3);
        margin-top: 8px;
    }
    
    .nav {
        display: flex;
        gap: 8px;
        margin-bottom: 24px;
        flex-wrap: wrap;
        justify-content: center;
    }
    
    .nav a {
        padding: 10px 20px;
        border-radius: 10px;
        color: var(--text2);
        text-decoration: none;
        font-weight: 500;
        background: var(--surface);
        border: 1px solid transparent;
        transition: all 0.3s;
    }
    
    .nav a:hover, .nav a.active {
        color: var(--primary);
        border-color: var(--primary);
    }
    
    .card {
        background: var(--surface2);
        border: 1px solid var(--border);
        border-radius: 14px;
        padding: 24px;
        margin-bottom: 20px;
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
    
    .grid { display: grid; gap: 20px; }
    .grid-2 { grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); }
    .grid-3 { grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); }
    
    .stat-card {
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 20px;
        text-align: center;
    }
    
    .stat-value {
        font-family: 'Orbitron', sans-serif;
        font-size: 2em;
        font-weight: 900;
        background: linear-gradient(135deg, var(--primary), var(--accent));
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    
    .stat-label {
        color: var(--text2);
        font-size: 0.85em;
        margin-top: 8px;
    }
    
    .form-group { margin-bottom: 16px; }
    
    .form-label {
        display: block;
        font-weight: 600;
        margin-bottom: 6px;
        color: var(--text2);
    }
    
    .form-input {
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
    
    .form-input:focus {
        border-color: var(--primary);
        box-shadow: 0 0 0 4px rgba(0,212,255,0.1);
    }
    
    textarea.form-input {
        min-height: 200px;
        resize: vertical;
    }
    
    .btn {
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
    }
    
    .btn-primary { background: linear-gradient(135deg, var(--success), #00c853); color: #000; }
    .btn-primary:hover { transform: translateY(-2px); }
    .btn-danger { background: var(--danger); color: #fff; }
    .btn-info { background: var(--primary); color: #000; }
    .btn-warning { background: var(--warning); color: #000; }
    .btn-sm { padding: 6px 14px; font-size: 0.8em; }
    .btn-block { width: 100%; justify-content: center; }
    
    table {
        width: 100%;
        border-collapse: collapse;
    }
    
    th, td {
        padding: 12px;
        text-align: left;
        border-bottom: 1px solid var(--border);
    }
    
    th { color: var(--primary); font-size: 0.8em; text-transform: uppercase; }
    
    .alert {
        padding: 14px;
        border-radius: 10px;
        margin: 14px 0;
        font-weight: 500;
    }
    
    .alert-success { background: rgba(0,230,118,0.1); border: 1px solid rgba(0,230,118,0.3); color: var(--success); }
    .alert-error { background: rgba(255,51,85,0.1); border: 1px solid rgba(255,51,85,0.3); color: var(--danger); }
    .alert-info { background: rgba(0,212,255,0.1); border: 1px solid rgba(0,212,255,0.3); color: var(--primary); }
    
    .badge {
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.75em;
        font-weight: 600;
    }
    
    .badge-success { background: rgba(0,230,118,0.15); color: var(--success); }
    .badge-danger { background: rgba(255,51,85,0.15); color: var(--danger); }
    .badge-info { background: rgba(0,212,255,0.15); color: var(--primary); }
    
    .code-editor {
        background: #000;
        border: 1px solid var(--border);
        border-radius: 10px;
        padding: 16px;
        font-family: 'JetBrains Mono', monospace;
        color: #00ff00;
        min-height: 300px;
    }
    
    .file-list {
        border: 1px solid var(--border);
        border-radius: 10px;
        overflow: hidden;
    }
    
    .file-item {
        padding: 10px 16px;
        border-bottom: 1px solid var(--border);
        display: flex;
        align-items: center;
        gap: 10px;
        cursor: pointer;
        transition: background 0.2s;
    }
    
    .file-item:hover { background: rgba(0,212,255,0.05); }
    .file-item:last-child { border-bottom: none; }
    
    .file-icon { color: var(--primary); width: 20px; }
    
    @media (max-width: 768px) {
        .logo { font-size: 1.8em; }
        .card { padding: 16px; }
        .grid-2, .grid-3 { grid-template-columns: 1fr; }
    }
</style>
"""

# ============================================
# ROTAS
# ============================================
@app.route('/')
def home():
    return render_template_string(f"""
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CyberHost - Hospedagem Web</title>
    {STYLE}
</head>
<body>
    <div class="app">
        <div class="header">
            <div class="logo">CYBERHOST</div>
            <div class="subtitle">HOSPEDAGEM WEB + GIT POBRE</div>
        </div>
        
        <div class="nav">
            <a href="/" class="active"><i class="fas fa-home"></i> Home</a>
            <a href="/login"><i class="fas fa-sign-in-alt"></i> Login</a>
            <a href="/register"><i class="fas fa-user-plus"></i> Cadastro</a>
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
                <div class="stat-value">∞</div>
                <div class="stat-label">Espaço</div>
            </div>
        </div>
        
        <div class="grid grid-2">
            <div class="card">
                <div class="card-title"><i class="fas fa-code"></i> Git Pobre</div>
                <p style="color:var(--text2);line-height:1.8;">
                    Sistema de controle de versão integrado. Crie repositórios, edite arquivos e faça deploy com um clique.
                </p>
                <ul style="color:var(--text3);list-style:none;margin-top:12px;">
                    <li>✅ Criação de repositórios</li>
                    <li>✅ Editor de código online</li>
                    <li>✅ Upload de arquivos</li>
                    <li>✅ Histórico de commits</li>
                </ul>
            </div>
            
            <div class="card">
                <div class="card-title"><i class="fas fa-rocket"></i> Deploy Automático</div>
                <p style="color:var(--text2);line-height:1.8;">
                    Hospede PHP, Python, JavaScript e HTML. Deploy instantâneo com subdomínio personalizado.
                </p>
                <ul style="color:var(--text3);list-style:none;margin-top:12px;">
                    <li>✅ Deploy com 1 clique</li>
                    <li>✅ Subdomínio: cyber-seunome</li>
                    <li>✅ Instalação automática de dependências</li>
                    <li>✅ Atualização automática</li>
                </ul>
            </div>
        </div>
        
        <a href="/register" class="btn btn-primary btn-block" style="margin-top:10px;">
            <i class="fas fa-rocket"></i> COMEÇAR AGORA
        </a>
    </div>
</body>
</html>
""")

@app.route('/login', methods=['GET', 'POST'])
def login_page():
    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        success, result = db.authenticate(username, password)
        if success:
            session['username'] = username
            session['is_admin'] = result.get('is_admin', False)
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
    <div class="app" style="max-width:450px;margin-top:60px;">
        <div class="header">
            <div class="logo" style="font-size:2em;">LOGIN</div>
        </div>
        <div class="card">
            {f'<div class="alert alert-error">{error}</div>' if error else ''}
            <form method="POST">
                <div class="form-group">
                    <label class="form-label">👤 Usuário</label>
                    <input type="text" name="username" class="form-input" required>
                </div>
                <div class="form-group">
                    <label class="form-label">🔒 Senha</label>
                    <input type="password" name="password" class="form-input" required>
                </div>
                <button type="submit" class="btn btn-primary btn-block">ENTRAR</button>
            </form>
            <p style="text-align:center;margin-top:16px;color:var(--text2);">
                Não tem conta? <a href="/register" style="color:var(--primary);">Cadastre-se</a>
            </p>
        </div>
    </div>
</body>
</html>
""")

@app.route('/register', methods=['GET', 'POST'])
def register_page():
    error = None
    success = None
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        email = request.form.get('email', '').strip()
        confirm = request.form.get('confirm_password', '')
        
        if not username or not password or not email:
            error = 'Preencha todos os campos!'
        elif len(username) < 3:
            error = 'Usuário muito curto!'
        elif password != confirm:
            error = 'Senhas não coincidem!'
        else:
            ok, msg = db.create_user(username, password, email)
            if ok:
                success = msg
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
    <div class="app" style="max-width:450px;margin-top:40px;">
        <div class="header">
            <div class="logo" style="font-size:2em;">CADASTRO</div>
        </div>
        <div class="card">
            {f'<div class="alert alert-error">{error}</div>' if error else ''}
            {f'<div class="alert alert-success">{success}</div>' if success else ''}
            <form method="POST">
                <div class="form-group">
                    <label class="form-label">👤 Usuário</label>
                    <input type="text" name="username" class="form-input" required minlength="3">
                </div>
                <div class="form-group">
                    <label class="form-label">📧 Email</label>
                    <input type="email" name="email" class="form-input" required>
                </div>
                <div class="form-group">
                    <label class="form-label">🔒 Senha</label>
                    <input type="password" name="password" class="form-input" required>
                </div>
                <div class="form-group">
                    <label class="form-label">🔒 Confirmar Senha</label>
                    <input type="password" name="confirm_password" class="form-input" required>
                </div>
                <button type="submit" class="btn btn-primary btn-block">CRIAR CONTA</button>
            </form>
        </div>
    </div>
</body>
</html>
""")

@app.route('/dashboard')
@login_required
def dashboard():
    username = session['username']
    user = db.users.get(username, {})
    repos = db.get_user_repos(username)
    
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
            <a href="/dashboard" class="active"><i class="fas fa-tachometer-alt"></i> Dashboard</a>
            <a href="/dashboard/repos"><i class="fas fa-code-branch"></i> Repositórios</a>
            <a href="/dashboard/new-repo"><i class="fas fa-plus"></i> Novo Repo</a>
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
            <div class="card-title"><i class="fas fa-list"></i> Seus Repositórios</div>
            {f'<div class="file-list">' + ''.join(f'''<div class="file-item" onclick="location.href='/dashboard/repo/{r["id"]}'" style="cursor:pointer;">
                <i class="fas fa-folder file-icon"></i>
                <span style="flex:1;"><strong>{r["name"]}</strong></span>
                <span class="badge badge-info">{r.get("language", "code")}</span>
                {f'<span class="badge badge-success" style="margin-left:8px;">Deploy: {r["deploy_url"]}</span>' if r.get("deploy_url") else ''}
                <i class="fas fa-chevron-right" style="color:var(--text3);"></i>
            </div>''' for r in repos.values()) + '</div>' if repos else '<p style="color:var(--text3);text-align:center;">Nenhum repositório ainda. <a href="/dashboard/new-repo" style="color:var(--primary);">Criar primeiro repo</a></p>'}
        </div>
    </div>
</body>
</html>
""")

@app.route('/dashboard/new-repo', methods=['GET', 'POST'])
@login_required
def new_repo():
    username = session['username']
    error = None
    
    if request.method == 'POST':
        repo_name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        
        if not repo_name:
            error = 'Nome do repositório é obrigatório!'
        elif not regex.match(r'^[a-zA-Z0-9_-]+$', repo_name):
            error = 'Nome inválido! Use apenas letras, números, - e _'
        else:
            ok, result = db.create_repo(username, repo_name, description)
            if ok:
                return redirect(url_for('dashboard'))
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
    <div class="app" style="max-width:600px;margin-top:40px;">
        <div class="card">
            <div class="card-title"><i class="fas fa-plus"></i> Novo Repositório</div>
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
                <button type="submit" class="btn btn-primary btn-block">CRIAR REPOSITÓRIO</button>
            </form>
        </div>
    </div>
</body>
</html>
""")

@app.route('/dashboard/repo/<repo_id>')
@login_required
def repo_view(repo_id):
    username = session['username']
    repo = db.repos.get(repo_id)
    
    if not repo or repo['owner'] != username:
        return "Repositório não encontrado!", 404
    
    files = GitPobre.get_files(username, repo['name'])
    
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
        <div class="header" style="text-align:left;">
            <div style="display:flex;align-items:center;gap:16px;">
                <a href="/dashboard" style="color:var(--text2);"><i class="fas fa-arrow-left"></i></a>
                <div>
                    <h2 style="color:var(--primary);">{repo['name']}</h2>
                    <p style="color:var(--text3);font-size:0.85em;">{repo.get('description', '')}</p>
                </div>
            </div>
        </div>
        
        <div class="nav">
            <a href="/dashboard/repo/{repo_id}"><i class="fas fa-code"></i> Arquivos</a>
            <a href="/dashboard/repo/{repo_id}/editor"><i class="fas fa-edit"></i> Novo Arquivo</a>
            <a href="/dashboard/repo/{repo_id}/upload"><i class="fas fa-upload"></i> Upload</a>
            <a href="/dashboard/repo/{repo_id}/deploy"><i class="fas fa-rocket"></i> Deploy</a>
            <a href="/dashboard/repo/{repo_id}/delete" style="color:var(--danger);" onclick="return confirm('Tem certeza?')"><i class="fas fa-trash"></i> Deletar</a>
        </div>
        
        {f'<div class="alert alert-info"><i class="fas fa-globe"></i> Deploy ativo: <a href="https://{repo["deploy_url"]}" target="_blank" style="color:var(--primary);">{repo["deploy_url"]}</a></div>' if repo.get('deploy_url') else ''}
        
        <div class="card">
            <div class="card-title"><i class="fas fa-folder-tree"></i> Arquivos ({len(files)})</div>
            <div class="file-list">
                {''.join(f'''
                <div class="file-item" onclick="location.href='/dashboard/repo/{repo_id}/file?path={f["path"]}'">
                    <i class="fas {'fa-folder' if f['type'] == 'folder' else 'fa-file-code'} file-icon"></i>
                    <span style="flex:1;">{f['name']}</span>
                    <span style="color:var(--text3);font-size:0.8em;">{f.get('size', 0)} bytes</span>
                </div>
                ''' for f in files)}
            </div>
        </div>
    </div>
</body>
</html>
""")

@app.route('/dashboard/repo/<repo_id>/editor', methods=['GET', 'POST'])
@login_required
def repo_editor(repo_id):
    username = session['username']
    repo = db.repos.get(repo_id)
    
    if not repo or repo['owner'] != username:
        return "Repositório não encontrado!", 404
    
    file_path = request.args.get('path', '')
    content = ''
    
    if file_path:
        content = GitPobre.get_file_content(username, repo['name'], file_path) or ''
    
    if request.method == 'POST':
        file_path = request.form.get('path', '').strip()
        content = request.form.get('content', '')
        
        if file_path:
            GitPobre.save_file(username, repo['name'], file_path, content)
            return redirect(url_for('repo_view', repo_id=repo_id))
    
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
        <div class="card">
            <div class="card-title"><i class="fas fa-edit"></i> {'Editar' if file_path else 'Novo'} Arquivo</div>
            <form method="POST">
                <div class="form-group">
                    <label class="form-label">📄 Caminho do Arquivo</label>
                    <input type="text" name="path" class="form-input" value="{file_path}" placeholder="index.html">
                </div>
                <div class="form-group">
                    <label class="form-label">📝 Conteúdo</label>
                    <textarea name="content" class="form-input" style="min-height:400px;font-family:'JetBrains Mono',monospace;">{content}</textarea>
                </div>
                <button type="submit" class="btn btn-primary btn-block">💾 SALVAR</button>
            </form>
        </div>
    </div>
</body>
</html>
""")

@app.route('/dashboard/repo/<repo_id>/upload', methods=['GET', 'POST'])
@login_required
def repo_upload(repo_id):
    username = session['username']
    repo = db.repos.get(repo_id)
    
    if not repo or repo['owner'] != username:
        return "Repositório não encontrado!", 404
    
    if request.method == 'POST':
        if 'file' not in request.files:
            return "Nenhum arquivo enviado!"
        
        file = request.files['file']
        if file.filename:
            GitPobre.upload_file(username, repo['name'], file)
            return redirect(url_for('repo_view', repo_id=repo_id))
    
    return render_template_string(f"""
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <title>Upload - {repo['name']}</title>
    {STYLE}
</head>
<body>
    <div class="app" style="max-width:600px;margin-top:40px;">
        <div class="card">
            <div class="card-title"><i class="fas fa-upload"></i> Upload de Arquivo</div>
            <form method="POST" enctype="multipart/form-data">
                <div class="form-group">
                    <label class="form-label">📁 Selecione o arquivo</label>
                    <input type="file" name="file" class="form-input" required>
                </div>
                <button type="submit" class="btn btn-primary btn-block">ENVIAR</button>
            </form>
        </div>
    </div>
</body>
</html>
""")

@app.route('/dashboard/repo/<repo_id>/deploy', methods=['GET', 'POST'])
@login_required
def repo_deploy(repo_id):
    username = session['username']
    repo = db.repos.get(repo_id)
    
    if not repo or repo['owner'] != username:
        return "Repositório não encontrado!", 404
    
    if request.method == 'POST':
        subdomain = request.form.get('subdomain', '').strip()
        ok, result = db.deploy_repo(repo_id, username, subdomain)
        if ok:
            return redirect(url_for('repo_view', repo_id=repo_id))
    
    return render_template_string(f"""
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <title>Deploy - {repo['name']}</title>
    {STYLE}
</head>
<body>
    <div class="app" style="max-width:600px;margin-top:40px;">
        <div class="card">
            <div class="card-title"><i class="fas fa-rocket"></i> Deploy do Site</div>
            <div class="card-desc" style="color:var(--text2);margin-bottom:20px;">
                Seu site ficará disponível em: <code style="background:var(--bg);padding:4px 8px;border-radius:4px;">cyber-SEUNOME.onrender.com</code>
            </div>
            <form method="POST">
                <div class="form-group">
                    <label class="form-label">🌐 Subdomínio (opcional)</label>
                    <input type="text" name="subdomain" class="form-input" placeholder="meu-app">
                    <small style="color:var(--text3);">Deixe em branco para usar: cyber-{username}-{repo['name']}</small>
                </div>
                <button type="submit" class="btn btn-primary btn-block">🚀 FAZER DEPLOY</button>
            </form>
        </div>
    </div>
</body>
</html>
""")

@app.route('/dashboard/repo/<repo_id>/file')
@login_required
def repo_file(repo_id):
    username = session['username']
    repo = db.repos.get(repo_id)
    
    if not repo or repo['owner'] != username:
        return "Repositório não encontrado!", 404
    
    file_path = request.args.get('path', '')
    content = GitPobre.get_file_content(username, repo['name'], file_path)
    
    if content is None:
        return "Arquivo não encontrado!", 404
    
    return render_template_string(f"""
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <title>{file_path} - {repo['name']}</title>
    {STYLE}
</head>
<body>
    <div class="app">
        <div class="card">
            <div class="card-title">
                <i class="fas fa-file-code"></i> {file_path}
                <a href="/dashboard/repo/{repo_id}/editor?path={file_path}" class="btn btn-info btn-sm" style="margin-left:auto;">Editar</a>
            </div>
            <div class="code-editor" style="white-space:pre-wrap;">{content}</div>
        </div>
    </div>
</body>
</html>
""")

@app.route('/dashboard/repo/<repo_id>/delete')
@login_required
def repo_delete(repo_id):
    username = session['username']
    db.delete_repo(repo_id, username)
    return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

@app.route('/ping')
def ping():
    return jsonify({'status': 'online'})

# ============================================
# AUTO-PING
# ============================================
def keep_alive():
    while True:
        try:
            http_requests.get(f"{Config.BASE_URL}/ping", timeout=10)
        except:
            pass
        time.sleep(300)

if __name__ == '__main__':
    threading.Thread(target=keep_alive, daemon=True).start()
    
    print(f"""
{Fore.CYAN}╔══════════════════════════════════════╗
║   {Fore.YELLOW}⚡ CYBERHOST v1.0 - ONLINE{Fore.CYAN}        ║
║   {Fore.WHITE}🌐 http://localhost:{Config.PORT}{Fore.CYAN}           ║
║   {Fore.WHITE}👑 admin: cyber / cybersecofcadm{Fore.CYAN}  ║
╚══════════════════════════════════════╝{Style.RESET_ALL}
    """)
    
    app.run(host='0.0.0.0', port=Config.PORT, debug=False, threaded=True)
