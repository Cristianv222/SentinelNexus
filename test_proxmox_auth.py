
from proxmoxer import ProxmoxAPI
from dotenv import load_dotenv
import os
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

load_dotenv()

def test_node(host, user, password, name):
    print(f"--------------------------------------------------")
    print(f"Testing Node: {name} ({host})")
    print(f"User: {user}")
    # Hide password for security in logs
    masked_pass = password[:2] + "*" * (len(password)-4) + password[-2:] if len(password) > 4 else "****"
    print(f"Pass: {masked_pass}")
    
    try:
        proxmox = ProxmoxAPI(
            host, 
            user=user, 
            password=password, 
            verify_ssl=False,
            timeout=10
        )
        
        # Try to get version to confirm auth
        version = proxmox.version.get()
        print(f"✅ SUCCESS! Connected to {host}")
        print(f"Server Version: {version['version']}")
        return True
    except Exception as e:
        print(f"❌ FAILED to connect to {host}")
        print(f"Error: {e}")
        return False

def main():
    print("🔍 TESTING PROXMOX AUTHENTICATION For ALL Nodes")
    
    nodes_count = 0
    success_count = 0
    
    # Iterate dynamically looking for PROXMOX_NODE{i}_HOST
    i = 1
    while True:
        host = os.getenv(f"PROXMOX_NODE{i}_HOST")
        if not host:
            break
            
        user = os.getenv(f"PROXMOX_NODE{i}_USER")
        password = os.getenv(f"PROXMOX_NODE{i}_PASSWORD")
        name = os.getenv(f"PROXMOX_NODE{i}_NAME", f"Node {i}")
        
        if test_node(host, user, password, name):
            success_count += 1
        
        nodes_count += 1
        i += 1
        
    print(f"--------------------------------------------------")
    print(f"SUMMARY: {success_count}/{nodes_count} Nodes Connected Successfully.")

if __name__ == "__main__":
    main()
