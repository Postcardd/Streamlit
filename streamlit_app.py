#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
import random
import time
import shutil
import re
import base64
import socket
import subprocess
import platform
from datetime import datetime
import uuid
from pathlib import Path
import urllib.request
import urllib.parse
import ssl
import tempfile
import argparse

# 全局变量
INSTALL_DIR = Path.home() / ".agsb"
CONFIG_FILE = INSTALL_DIR / "config.json"
SB_PID_FILE = INSTALL_DIR / "sbpid.log"
ARGO_PID_FILE = INSTALL_DIR / "sbargopid.log"
LIST_FILE = INSTALL_DIR / "list.txt"
LOG_FILE = INSTALL_DIR / "argo.log"
DEBUG_LOG = INSTALL_DIR / "python_debug.log"
CUSTOM_DOMAIN_FILE = INSTALL_DIR / "custom_domain.txt"

# ====== 全局可配置参数 ======
USER_NAME = os.getenv("USER_NAME")
UUID = os.getenv("UUID")
PORT = os.getenv("PORT")
DOMAIN = os.getenv("DOMAIN")
CF_TOKEN = os.getenv("CF_TOKEN")
# =========================================

def parse_args():
    parser = argparse.ArgumentParser(description="ArgoSB Python3 一键脚本 (VLESS + Argo)")
    parser.add_argument("action", nargs="?", default="install",
                        choices=["install", "status", "update", "del", "uninstall", "cat"],
                        help="操作类型")
    parser.add_argument("--domain", "-d", dest="agn", help="设置自定义域名")
    parser.add_argument("--uuid", "-u", help="设置自定义UUID")
    parser.add_argument("--port", "-p", dest="vmpt", type=int, help="设置自定义VLESS端口")
    parser.add_argument("--agk", "--token", dest="agk", help="设置 Argo Tunnel Token")
    parser.add_argument("--user", "-U", dest="user", help="设置用户名")

    return parser.parse_args()

def http_get(url, timeout=10):
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, context=ctx, timeout=timeout) as response:
            return response.read().decode('utf-8')
    except Exception as e:
        print(f"HTTP请求失败: {url}, 错误: {e}")
        write_debug_log(f"HTTP GET Error: {url}, {e}")
        return None

def download_file(url, target_path, mode='wb'):
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, context=ctx) as response, open(target_path, mode) as out_file:
            shutil.copyfileobj(response, out_file)
        return True
    except Exception as e:
        print(f"下载文件失败: {url}, 错误: {e}")
        write_debug_log(f"Download Error: {url}, {e}")
        return False

def print_info():
    print("\033[36m╭───────────────────────────────────────────────────────────────╮\033[0m")
    print("\033[36m│             \033[33m✨ ArgoSB Python3 VLESS 修复版 ✨              \033[36m│\033[0m")
    print("\033[36m├───────────────────────────────────────────────────────────────┤\033[0m")
    print("\033[36m│ \033[32m协议: VLESS + WebSocket + Argo Tunnel                     \033[36m│\033[0m")
    print("\033[36m│ \033[32m版本: 25.7.1-fix                                          \033[36m│\033[0m")
    print("\033[36m╰───────────────────────────────────────────────────────────────╯\033[0m")

def write_debug_log(message):
    try:
        if not INSTALL_DIR.exists():
            INSTALL_DIR.mkdir(parents=True, exist_ok=True)
        with open(DEBUG_LOG, 'a', encoding='utf-8') as f:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            f.write(f"[{timestamp}] {message}\n")
    except Exception as e:
        print(f"写入日志失败: {e}")

def download_binary(name, download_url, target_path):
    print(f"正在下载 {name}...")
    success = download_file(download_url, target_path)
    if success:
        print(f"{name} 下载成功!")
        os.chmod(target_path, 0o755)
        return True
    else:
        print(f"{name} 下载失败!")
        return False

def generate_vless_link(config):
    """生成标准 VLESS 分享链接"""
    uuid_str = config.get("id", "")
    address = config.get("add", "")
    port = str(config.get("port", "443"))
    name = urllib.parse.quote(config.get("ps", "ArgoSB"), safe='')
    
    params = {
        "encryption": "none",
        "type": config.get("net", "ws"),
        "host": config.get("host", "")
    }
    
    path = config.get("path", "")
    if path:
        params["path"] = path
    
    if config.get("tls"):
        params["security"] = config.get("tls")
        if config.get("sni"):
            params["sni"] = config.get("sni")
    else:
        params["security"] = "none"
    
    query_parts = []
    for k, v in params.items():
        if k == "path":
            # 保留 /，但编码 ? = 等特殊字符
            encoded_v = urllib.parse.quote(str(v), safe='/')
        else:
            encoded_v = urllib.parse.quote(str(v), safe='')
        query_parts.append(f"{k}={encoded_v}")
    
    query = "&".join(query_parts)
    return f"vless://{uuid_str}@{address}:{port}?{query}#{name}"

def generate_links(domain, port_vm_ws, uuid_str, user_name=None):
    write_debug_log(f"生成链接: domain={domain}, port_vm_ws={port_vm_ws}, uuid_str={uuid_str}")

    ws_path = f"/{uuid_str[:8]}-vl"
    ws_path_full = f"{ws_path}?ed=2048"
    write_debug_log(f"WebSocket路径: {ws_path_full}")

    hostname = socket.gethostname()[:10]
    all_links = []
    link_names = []

    cf_ips_tls = {
        "104.16.0.0": "443", "104.17.0.0": "8443", "104.18.0.0": "2053",
        "104.19.0.0": "2083", "104.20.0.0": "2087"
    }
    cf_ips_http = {
        "104.21.0.0": "80", "104.22.0.0": "8080", "104.24.0.0": "8880"
    }

    for ip, port_cf in cf_ips_tls.items():
        ps_name = f"VLESS-TLS-{hostname}-{ip.split('.')[2]}-{port_cf}"
        config = {
            "ps": ps_name, "add": ip, "port": port_cf, "id": uuid_str,
            "net": "ws", "host": domain, "path": ws_path_full,
            "tls": "tls", "sni": domain
        }
        all_links.append(generate_vless_link(config))
        link_names.append(f"TLS-{port_cf}-{ip}")

    for ip, port_cf in cf_ips_http.items():
        ps_name = f"VLESS-HTTP-{hostname}-{ip.split('.')[2]}-{port_cf}"
        config = {
            "ps": ps_name, "add": ip, "port": port_cf, "id": uuid_str,
            "net": "ws", "host": domain, "path": ws_path_full,
            "tls": ""
        }
        all_links.append(generate_vless_link(config))
        link_names.append(f"HTTP-{port_cf}-{ip}")
    
    direct_tls_config = {
        "ps": f"VLESS-TLS-{hostname}-Direct-{domain[:15]}-443", 
        "add": domain, "port": "443", "id": uuid_str,
        "net": "ws", "host": domain, "path": ws_path_full,
        "tls": "tls", "sni": domain
    }
    all_links.append(generate_vless_link(direct_tls_config))
    link_names.append(f"TLS-Direct-{domain}-443")

    direct_http_config = {
        "ps": f"VLESS-HTTP-{hostname}-Direct-{domain[:15]}-80",
        "add": domain, "port": "80", "id": uuid_str,
        "net": "ws", "host": domain, "path": ws_path_full,
        "tls": ""
    }
    all_links.append(generate_vless_link(direct_http_config))
    link_names.append(f"HTTP-Direct-{domain}-80")

    (INSTALL_DIR / "allnodes.txt").write_text("\n".join(all_links) + "\n")
    (INSTALL_DIR / "jh.txt").write_text("\n".join(all_links) + "\n") 
    CUSTOM_DOMAIN_FILE.write_text(domain)

    list_content_color_file = []
    list_content_color_file.append("\033[36m╭───────────────────────────────────────────────────────────────╮\033[0m")
    list_content_color_file.append("\033[36m│                \033[33m✨ ArgoSB 节点信息 ✨                   \033[36m│\033[0m")
    list_content_color_file.append("\033[36m├───────────────────────────────────────────────────────────────┤\033[0m")
    list_content_color_file.append(f"\033[36m│ \033[32m域名 (Domain): \033[0m{domain}")
    list_content_color_file.append(f"\033[36m│ \033[32mUUID: \033[0m{uuid_str}")
    list_content_color_file.append(f"\033[36m│ \033[32m本地VLESS端口: \033[0m{port_vm_ws}")
    list_content_color_file.append(f"\033[36m│ \033[32mWebSocket路径: \033[0m{ws_path_full}")
    list_content_color_file.append("\033[36m├───────────────────────────────────────────────────────────────┤\033[0m")
    list_content_color_file.append("\033[36m│ \033[33m所有节点列表:\033[0m")
    for i, (link, name) in enumerate(zip(all_links, link_names)):
        list_content_color_file.append(f"\033[36m│ \033[32m{i+1}. {name}:\033[0m")
        list_content_color_file.append(f"\033[36m│ \033[0m{link}")
        if i < len(all_links) -1 :
             list_content_color_file.append("\033[36m│ \033[0m")
    list_content_color_file.append("\033[36m├───────────────────────────────────────────────────────────────┤\033[0m")
    list_content_color_file.append("\033[36m│ \033[33m使用方法:\033[0m")
    list_content_color_file.append("\033[36m│ \033[32m查看节点: \033[0mpython3 " + os.path.basename(__file__) + " status")
    list_content_color_file.append("\033[36m│ \033[32m单行节点: \033[0mpython3 " + os.path.basename(__file__) + " cat")
    list_content_color_file.append("\033[36m│ \033[32m卸载脚本: \033[0mpython3 " + os.path.basename(__file__) + " del")
    list_content_color_file.append("\033[36m╰───────────────────────────────────────────────────────────────╯\033[0m")
    LIST_FILE.write_text("\n".join(list_content_color_file) + "\n")

    print("\033[36m╭───────────────────────────────────────────────────────────────╮\033[0m")
    print("\033[36m│                \033[33m✨ ArgoSB 安装成功! ✨                    \033[36m│\033[0m")
    print("\033[36m├───────────────────────────────────────────────────────────────┤\033[0m")
    print(f"\033[36m│ \033[32m域名 (Domain): \033[0m{domain}")
    print(f"\033[36m│ \033[32mUUID: \033[0m{uuid_str}")
    print(f"\033[36m│ \033[32m本地VLESS端口: \033[0m{port_vm_ws}")
    print(f"\033[36m│ \033[32mWebSocket路径: \033[0m{ws_path_full}")
    print("\033[36m├───────────────────────────────────────────────────────────────┤\033[0m")
    print("\033[36m│ \033[33m所有节点链接:\033[0m")
    
    for i, link in enumerate(all_links):
        print(f"\033[36m│ \033[32m{i+1}. {link_names[i]}:\033[0m")
        print(f"\033[36m│ \033[0m{link}")
        if i < len(all_links) - 1:
            print("\033[36m│ \033[0m") 
    
    print("\033[36m├───────────────────────────────────────────────────────────────┤\033[0m")
    print(f"\033[36m│ \033[32m节点文件: \033[0m{LIST_FILE}")
    print(f"\033[36m│ \033[32m纯链接文件: \033[0m{INSTALL_DIR / 'allnodes.txt'}")
    print("\033[36m│ \033[32m使用 \033[33mpython3 " + os.path.basename(__file__) + " status\033[32m 查看状态\033[0m")
    print("\033[36m│ \033[32m使用 \033[33mpython3 " + os.path.basename(__file__) + " cat\033[32m 查看单行节点\033[0m")
    print("\033[36m╰───────────────────────────────────────────────────────────────╯\033[0m")
    
    print()
    print("\033[33m以下为所有节点的纯单行链接 (可直接复制):\033[0m")
    print("\033[34m--------------------------------------------------------\033[0m")
    for link in all_links:
        print(link)
    print("\033[34m--------------------------------------------------------\033[0m")
    print()
    
    if user_name:
        all_links_b64 = base64.b64encode("\n".join(all_links).encode()).decode()
        upload_to_api(all_links_b64, user_name)
    
    write_debug_log(f"链接生成完毕。")
    return all_links

def install(args):
    if not INSTALL_DIR.exists():
        INSTALL_DIR.mkdir(parents=True, exist_ok=True)
    os.chdir(INSTALL_DIR)
    write_debug_log("开始安装过程")

    user_name = args.user or os.environ.get("user") or USER_NAME
    if not user_name:
        user_name = input("请输入用户名（用于上传文件名）: ").strip()
        if not user_name:
            print("用户名不能为空！")
            sys.exit(1)
    print(f"使用用户名: {user_name}")
    write_debug_log(f"User: {user_name}")

    uuid_str = args.uuid or os.environ.get("uuid") or UUID
    if not uuid_str:
        uuid_input = input("请输入自定义UUID (留空则随机生成): ").strip()
        uuid_str = uuid_input or str(uuid.uuid4())
    print(f"使用 UUID: {uuid_str}")
    write_debug_log(f"UUID: {uuid_str}")

    port_vm_ws_str = str(args.vmpt) if args.vmpt else os.environ.get("vmpt") or str(PORT)
    if not port_vm_ws_str or port_vm_ws_str == "0":
        port_vm_ws_str = input(f"请输入自定义VLESS端口 (10000-65535, 留空随机): ").strip()
    if port_vm_ws_str:
        try:
            port_vm_ws = int(port_vm_ws_str)
            if not (10000 <= port_vm_ws <= 65535):
                print("端口号无效，将使用随机端口。")
                port_vm_ws = random.randint(10000, 65535)
        except ValueError:
            print("端口输入非数字，将使用随机端口。")
            port_vm_ws = random.randint(10000, 65535)
    else:
        port_vm_ws = random.randint(10000, 65535)
    print(f"使用 VLESS 本地端口: {port_vm_ws}")
    write_debug_log(f"VLESS Port: {port_vm_ws}")

    argo_token = args.agk or os.environ.get("agk") or CF_TOKEN
    if not argo_token:
        argo_token_input = input("请输入 Argo Tunnel Token (留空则使用临时隧道): ").strip()
        argo_token = argo_token_input or None
    if argo_token:
        print(f"使用 Argo Tunnel Token: ******{argo_token[-6:]}")
        write_debug_log(f"Argo Token: Present")
    else:
        print("未提供 Argo Tunnel Token，将使用临时隧道。")
        write_debug_log("Argo Token: Not provided")

    custom_domain = args.agn or os.environ.get("agn") or DOMAIN
    if not custom_domain:
        domain_prompt = "请输入自定义域名"
        if argo_token:
            domain_prompt += " (必须与Argo Token关联)"
        else:
            domain_prompt += " (留空自动获取 trycloudflare.com)"
        domain_prompt += ": "
        custom_domain_input = input(domain_prompt).strip()
        custom_domain = custom_domain_input or None
    if custom_domain:
        print(f"使用自定义域名: {custom_domain}")
        write_debug_log(f"Custom Domain: {custom_domain}")
    elif argo_token:
        print("\033[31m错误: 使用 Argo Token 时必须提供自定义域名。\033[0m")
        sys.exit(1)
    else:
        print("未提供自定义域名，将尝试自动获取。")

    system = platform.system().lower()
    machine = platform.machine().lower()
    arch = ""
    if system == "linux":
        if "x86_64" in machine or "amd64" in machine: arch = "amd64"
        elif "aarch64" in machine or "arm64" in machine: arch = "arm64"
        elif "armv7" in machine: arch = "arm"
        else: arch = "amd64"
    else:
        print(f"不支持的系统: {system}")
        sys.exit(1)
    write_debug_log(f"系统: {system}, 架构: {machine}, 使用: {arch}")

    singbox_path = INSTALL_DIR / "sing-box"
    if not singbox_path.exists():
        try:
            print("获取 sing-box 最新版本...")
            version_info = http_get("https://api.github.com/repos/SagerNet/sing-box/releases/latest")
            sb_version = json.loads(version_info)["tag_name"].lstrip("v") if version_info else "1.10.0"
            print(f"sing-box 版本: {sb_version}")
        except Exception as e:
            sb_version = "1.10.0"
            print(f"获取版本失败，使用默认: {sb_version}")
        sb_name_actual = f"sing-box-{sb_version}-linux-{arch}"
        if arch == "arm": sb_name_actual = f"sing-box-{sb_version}-linux-armv7"
        sb_url = f"https://github.com/SagerNet/sing-box/releases/download/v{sb_version}/{sb_name_actual}.tar.gz"
        tar_path = INSTALL_DIR / "sing-box.tar.gz"
        if not download_file(sb_url, tar_path):
            sb_url_backup = f"https://github.91chi.fun/https://github.com/SagerNet/sing-box/releases/download/v{sb_version}/{sb_name_actual}.tar.gz"
            if not download_file(sb_url_backup, tar_path):
                print("sing-box 下载失败")
                sys.exit(1)
        try:
            print("解压 sing-box...")
            import tarfile
            with tarfile.open(tar_path, "r:gz") as tar:
                tar.extractall(path=INSTALL_DIR)
            extracted = INSTALL_DIR / sb_name_actual
            if not extracted.exists():
                 extracted = INSTALL_DIR / f"sing-box-{sb_version}-linux-{arch}"
            shutil.move(extracted / "sing-box", singbox_path)
            shutil.rmtree(extracted)
            tar_path.unlink()
            os.chmod(singbox_path, 0o755)
        except Exception as e:
            print(f"解压 sing-box 失败: {e}")
            sys.exit(1)

    cloudflared_path = INSTALL_DIR / "cloudflared"
    if not cloudflared_path.exists():
        cf_arch = arch
        cf_url = f"https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-{cf_arch}"
        if not download_binary("cloudflared", cf_url, cloudflared_path):
            cf_url_backup = f"https://github.91chi.fun/https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-{cf_arch}"
            if not download_binary("cloudflared", cf_url_backup, cloudflared_path):
                print("cloudflared 下载失败")
                sys.exit(1)

    config_data = {
        "user_name": user_name,
        "uuid_str": uuid_str,
        "port_vm_ws": port_vm_ws,
        "argo_token": argo_token,
        "custom_domain_agn": custom_domain,
        "install_date": datetime.now().strftime('%Y%m%d%H%M')
    }
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config_data, f, indent=2)
    write_debug_log(f"配置文件已生成")

    create_sing_box_config(port_vm_ws, uuid_str)
    create_startup_script()
    setup_autostart()
    start_services()

    if argo_token:
        print("\033[33m提示: 使用命名隧道时，请确保在 Cloudflare Zero Trust 控制台已配置 Public Hostname")
        print(f"  Ingress 规则应指向: http://localhost:{port_vm_ws}\033[0m")

    final_domain = custom_domain
    if not argo_token and not custom_domain:
        print("等待临时隧道域名生成...")
        final_domain = get_tunnel_domain()
        if not final_domain:
            print("\033[31m无法获取临时域名，请检查 argo.log\033[0m")
            print(f"  手动指定: python3 {os.path.basename(__file__)} --agn your-domain.com")
            sys.exit(1)
    elif argo_token and not custom_domain:
        sys.exit(1)

    if final_domain:
        generate_links(final_domain, port_vm_ws, uuid_str, user_name)
    else:
        print("\033[31m最终域名未能确定\033[0m")
        sys.exit(1)

def setup_autostart():
    try:
        crontab_list = subprocess.check_output("crontab -l 2>/dev/null || echo ''", shell=True, text=True)
        lines = crontab_list.splitlines()
        script_name_sb = str((INSTALL_DIR / "start_sb.sh").resolve())
        script_name_cf = str((INSTALL_DIR / "start_cf.sh").resolve())

        filtered_lines = [
            line for line in lines 
            if script_name_sb not in line and script_name_cf not in line and line.strip()
        ]
        filtered_lines.append(f"@reboot {script_name_sb} >/dev/null 2>&1")
        filtered_lines.append(f"@reboot {script_name_cf} >/dev/null 2>&1")
        new_crontab = "\n".join(filtered_lines).strip() + "\n"
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp:
            tmp.write(new_crontab)
            tmp_path = tmp.name
        subprocess.run(f"crontab {tmp_path}", shell=True, check=True)
        os.unlink(tmp_path)
        print("开机自启动设置成功。")
    except Exception as e:
        print(f"设置开机自启动失败: {e}")

def uninstall():
    print("开始卸载...")
    for pid_file_path in [SB_PID_FILE, ARGO_PID_FILE]:
        if pid_file_path.exists():
            try:
                pid = pid_file_path.read_text().strip()
                if pid:
                    os.system(f"kill {pid} 2>/dev/null || true")
            except Exception as e:
                print(f"停止进程出错: {e}")
    time.sleep(1)
    os.system("pkill -9 -f 'sing-box run -c sb.json' 2>/dev/null || true")
    os.system("pkill -9 -f 'cloudflared tunnel' 2>/dev/null || true")

    try:
        crontab_list = subprocess.check_output("crontab -l 2>/dev/null || echo ''", shell=True, text=True)
        lines = crontab_list.splitlines()
        script_name_sb = str((INSTALL_DIR / "start_sb.sh").resolve())
        script_name_cf = str((INSTALL_DIR / "start_cf.sh").resolve())
        filtered_lines = [
            line for line in lines
            if script_name_sb not in line and script_name_cf not in line and line.strip()
        ]
        new_crontab = "\n".join(filtered_lines).strip()
        if not new_crontab:
            subprocess.run("crontab -r", shell=True, check=False)
        else:
            with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp:
                tmp.write(new_crontab + "\n")
                tmp_path = tmp.name
            subprocess.run(f"crontab {tmp_path}", shell=True, check=True)
            os.unlink(tmp_path)
    except Exception as e:
        print(f"移除 crontab 出错: {e}")

    if INSTALL_DIR.exists():
        try:
            shutil.rmtree(INSTALL_DIR)
            print(f"安装目录 {INSTALL_DIR} 已删除。")
        except Exception as e:
            print(f"删除安装目录失败: {e}")
    print("卸载完成。")
    sys.exit(0)

def upgrade():
    script_url = "https://raw.githubusercontent.com/yonggekkk/argosb/main/agsb_custom_domain.py"
    print(f"下载最新脚本...")
    try:
        script_content = http_get(script_url)
        if script_content:
            script_path = Path(__file__).resolve()
            backup_path = script_path.with_suffix(".bak")
            shutil.copyfile(script_path, backup_path)
            with open(script_path, 'w', encoding='utf-8') as f:
                f.write(script_content)
            os.chmod(script_path, 0o755)
            print("\033[32m升级完成！请重新运行。\033[0m")
        else:
            print("\033[31m下载失败。\033[0m")
    except Exception as e:
        print(f"\033[31m升级出错: {e}\033[0m")
    sys.exit(0)

def check_status():
    sb_running = SB_PID_FILE.exists() and os.path.exists(f"/proc/{SB_PID_FILE.read_text().strip()}")
    cf_running = ARGO_PID_FILE.exists() and os.path.exists(f"/proc/{ARGO_PID_FILE.read_text().strip()}")

    if sb_running and cf_running and LIST_FILE.exists():
        print("\033[36m╭───────────────────────────────────────────────────────────────╮\033[0m")
        print("\033[36m│                \033[33m✨ ArgoSB 运行状态 ✨                    \033[36m│\033[0m")
        print("\033[36m├───────────────────────────────────────────────────────────────┤\033[0m")
        print("\033[36m│ \033[32m服务状态: \033[33m运行中\033[0m")
        
        domain_to_display = "未知"
        if CUSTOM_DOMAIN_FILE.exists():
            domain_to_display = CUSTOM_DOMAIN_FILE.read_text().strip()
            print(f"\033[36m│ \033[32m当前域名: \033[0m{domain_to_display}")
        elif CONFIG_FILE.exists():
            config = json.loads(CONFIG_FILE.read_text())
            if config.get("custom_domain_agn"):
                 domain_to_display = config["custom_domain_agn"]
                 print(f"\033[36m│ \033[32m配置域名: \033[0m{domain_to_display}")
            elif not config.get("argo_token") and LOG_FILE.exists():
                log_content = LOG_FILE.read_text()
                match = re.search(r'https://([a-zA-Z0-9.-]+\.trycloudflare\.com)', log_content)
                if match:
                    domain_to_display = match.group(1)
                    print(f"\033[36m│ \033[32mArgo临时域名: \033[0m{domain_to_display}")
        
        if domain_to_display == "未知":
             print("\033[36m│ \033[31m域名信息未找到\033[0m")

        print("\033[36m├───────────────────────────────────────────────────────────────┤\033[0m")
        if (INSTALL_DIR / "allnodes.txt").exists():
            print("\033[36m│ \033[33m节点链接 (前3条):\033[0m")
            with open(INSTALL_DIR / "allnodes.txt", 'r') as f:
                links = f.read().splitlines()
                for i in range(min(3, len(links))):
                    print(f"\033[36m│ \033[0m{links[i][:70]}...")
            if len(links) > 3:
                print("\033[36m│ \033[32m... 更多节点请使用 'cat' 查看 ...\033[0m")
        print("\033[36m╰───────────────────────────────────────────────────────────────╯\033[0m")
        return True
    
    status_msgs = []
    if not sb_running: status_msgs.append("sing-box 未运行")
    if not cf_running: status_msgs.append("cloudflared 未运行")
    if not LIST_FILE.exists(): status_msgs.append("节点文件未生成")

    print("\033[36m╭───────────────────────────────────────────────────────────────╮\033[0m")
    print("\033[36m│                \033[33m✨ ArgoSB 运行状态 ✨                    \033[36m│\033[0m")
    print("\033[36m├───────────────────────────────────────────────────────────────┤\033[0m")
    for msg in status_msgs:
        print(f"\033[36m│   - \033[31m{msg}\033[0m")
    print("\033[36m│ \033[32m尝试重装: \033[33mpython3 " + os.path.basename(__file__) + " install\033[0m")
    print("\033[36m╰───────────────────────────────────────────────────────────────╯\033[0m")
    return False

def create_sing_box_config(port_vm_ws, uuid_str):
    """创建 sing-box VLESS WebSocket 入站配置"""
    write_debug_log(f"创建 sing-box 配置，端口: {port_vm_ws}")
    ws_path = f"/{uuid_str[:8]}-vl"

    config_dict = {
        "log": {"level": "info", "timestamp": True},
        "inbounds": [{
            "type": "vless",
            "tag": "vless-in",
            "listen": "127.0.0.1",
            "listen_port": port_vm_ws,
            "tcp_fast_open": False,
            "sniff": True,
            "sniff_override_destination": False,
            "proxy_protocol": False,
            "users": [{"uuid": uuid_str}],
            "transport": {
                "type": "ws",
                "path": ws_path,
                "max_early_data": 2048,
                "early_data_header_name": "Sec-WebSocket-Protocol"
            }
        }],
        "outbounds": [{"type": "direct", "tag": "direct"}]
    }
    sb_config_file = INSTALL_DIR / "sb.json"
    with open(sb_config_file, 'w') as f:
        json.dump(config_dict, f, indent=2)
    write_debug_log(f"sing-box 配置已写入: {sb_config_file}")

def create_startup_script():
    if not CONFIG_FILE.exists():
        print("配置文件不存在，请先执行安装。")
        return

    config = json.loads(CONFIG_FILE.read_text())
    port_vm_ws = config["port_vm_ws"]
    uuid_str = config["uuid_str"]
    argo_token = config.get("argo_token")
    
    sb_start_script_path = INSTALL_DIR / "start_sb.sh"
    sb_start_content = f'''#!/bin/bash
cd {INSTALL_DIR.resolve()}
./sing-box run -c sb.json > sb.log 2>&1 &
echo $! > {SB_PID_FILE.name}
'''
    sb_start_script_path.write_text(sb_start_content)
    os.chmod(sb_start_script_path, 0o755)

    cf_start_script_path = INSTALL_DIR / "start_cf.sh"
    cf_cmd_base = f"./cloudflared tunnel --no-autoupdate"

    if argo_token:
        cf_cmd = f"{cf_cmd_base} run --token {argo_token}"
    else:
        # 修复: --url 只到端口，不能带路径
        cf_cmd = f"{cf_cmd_base} --url http://localhost:{port_vm_ws} --edge-ip-version auto --protocol http2"
    
    cf_start_content = f'''#!/bin/bash
cd {INSTALL_DIR.resolve()}
{cf_cmd} > {LOG_FILE.name} 2>&1 &
echo $! > {ARGO_PID_FILE.name}
'''
    cf_start_script_path.write_text(cf_start_content)
    os.chmod(cf_start_script_path, 0o755)
    write_debug_log("启动脚本已创建。")

def verify_services():
    """验证服务是否正常启动"""
    issues = []
    
    sb_pid = SB_PID_FILE.read_text().strip() if SB_PID_FILE.exists() else None
    sb_running = sb_pid and sb_pid.isdigit() and os.path.exists(f"/proc/{sb_pid}")
    
    if not sb_running:
        issues.append("sing-box 进程未运行")
    else:
        if CONFIG_FILE.exists():
            try:
                config = json.loads(CONFIG_FILE.read_text())
                port = config.get("port_vm_ws")
                if port:
                    result = subprocess.run(f"ss -tln 2>/dev/null | grep -q ':{port}'", shell=True)
                    if result.returncode != 0:
                        result2 = subprocess.run(f"netstat -tln 2>/dev/null | grep -q ':{port}'", shell=True)
                        if result2.returncode != 0:
                            issues.append(f"sing-box 未监听端口 {port}")
            except Exception as e:
                write_debug_log(f"端口检查出错: {e}")

    cf_pid = ARGO_PID_FILE.read_text().strip() if ARGO_PID_FILE.exists() else None
    cf_running = cf_pid and cf_pid.isdigit() and os.path.exists(f"/proc/{cf_pid}")
    
    if not cf_running:
        issues.append("cloudflared 进程未运行")
    else:
        if LOG_FILE.exists():
            try:
                log_content = LOG_FILE.read_text()
                if "ERR" in log_content:
                    lines = log_content.splitlines()
                    err_lines = [l for l in lines if "ERR" in l][-2:]
                    issues.append(f"cloudflared 错误: {'; '.join(err_lines)}")
            except Exception as e:
                write_debug_log(f"日志检查出错: {e}")
    
    return len(issues) == 0, issues

def start_services():
    print("启动 sing-box...")
    subprocess.run(str(INSTALL_DIR / "start_sb.sh"), shell=True)
    
    print("启动 cloudflared...")
    subprocess.run(str(INSTALL_DIR / "start_cf.sh"), shell=True)
    
    print("等待服务初始化 (5秒)...")
    time.sleep(5)
    
    ok, issues = verify_services()
    if not ok:
        print("\033[31m服务启动验证失败:\033[0m")
        for issue in issues:
            print(f"  - {issue}")
        print("\033[33m诊断建议:\033[0m")
        print("  1. cat ~/.agsb/sb.log    (sing-box 日志)")
        print("  2. cat ~/.agsb/argo.log  (cloudflared 日志)")
        print("  3. 检查端口是否被占用: ss -tln | grep <端口>")
    else:
        print("\033[32m服务启动验证通过。\033[0m")
    
    write_debug_log("服务启动完成。")

def get_tunnel_domain():
    retry_count = 0
    max_retries = 15
    while retry_count < max_retries:
        if LOG_FILE.exists():
            try:
                log_content = LOG_FILE.read_text()
                match = re.search(r'https://([a-zA-Z0-9.-]+\.trycloudflare\.com)', log_content)
                if match:
                    domain = match.group(1)
                    write_debug_log(f"获取到临时域名: {domain}")
                    print(f"获取到临时域名: {domain}")
                    return domain
            except Exception as e:
                write_debug_log(f"解析日志出错: {e}")
        
        retry_count += 1
        print(f"等待域名生成... ({retry_count}/{max_retries})")
        time.sleep(3)
    
    write_debug_log("获取临时域名超时")
    return None

UPLOAD_API = "https://mem.ip-ddns.com/api/upload.php"

def upload_to_api(subscription_content, user_name):
    try:
        import requests
    except ImportError:
        print("安装 requests...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
            import requests
        except Exception as e:
            print(f"安装失败: {e}")
            return False
    
    try:
        file_name = f"{user_name}.txt"
        temp_file = INSTALL_DIR / file_name
        with open(str(temp_file), 'w', encoding='utf-8') as f:
            f.write(subscription_content)
        
        files = {'file': (file_name, open(str(temp_file), 'rb'))}
        response = requests.post(UPLOAD_API, files=files)
        files['file'][1].close()
        if os.path.exists(str(temp_file)):
            os.remove(str(temp_file))
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success') or result.get('url'):
                url = result.get('url', '')
                print(f"\033[36m│ \033[32m订阅上传成功: {url}\033[0m")
                with open(str(INSTALL_DIR / "subscription_url.txt"), 'w') as f:
                    f.write(url)
                return True
        print(f"上传失败: {response.status_code}")
        return False
    except Exception as e:
        print(f"上传出错: {e}")
        return False

def main():
    print_info()
    args = parse_args()

    if args.action == "install":
        install(args)
    elif args.action in ["uninstall", "del"]:
        uninstall()
    elif args.action == "update":
        upgrade()
    elif args.action == "status":
        check_status()
    elif args.action == "cat":
        all_nodes_path = INSTALL_DIR / "allnodes.txt"
        if all_nodes_path.exists():
            print(all_nodes_path.read_text().strip())
        else:
            print(f"\033[31m节点文件未找到\033[0m")
    else:
        if INSTALL_DIR.exists() and CONFIG_FILE.exists():
            print("\033[33m检测到可能已安装。\033[0m")
            if check_status():
                 print(f"\033[32m如需重装先卸载: python3 {os.path.basename(__file__)} del\033[0m")
            else:
                install(args)
        else:
            install(args)

if __name__ == "__main__":
    script_name = os.path.basename(__file__)
    if len(sys.argv) == 1:
        if INSTALL_DIR.exists() and CONFIG_FILE.exists():
            print(f"\033[33m检测到已安装，显示状态。\033[0m")
            check_status()
        else:
            print(f"\033[33m开始安装...\033[0m")
            args = parse_args()
            install(args)
    else:
        main()
