import os
import subprocess
import sys

def parse_env_file(filepath):
    vars_dict = {}
    if not os.path.exists(filepath):
        print(f"Warning: {filepath} not found.")
        return vars_dict
    
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                key, val = line.split('=', 1)
                vars_dict[key.strip()] = val.strip()
    return vars_dict

def set_vars(service_name, vars_dict):
    if not vars_dict:
        return
    
    print(f"Setting variables for service: {service_name}")
    # Construct command: railway variable set key=value key2=value2 --service service_name --skip-deploys
    # Wait, check if multiple args are supported. Usually yes.
    # If not, loop.
    
    cmd = ["railway", "variable", "set"]
    for k, v in vars_dict.items():
        cmd.append(f"{k}={v}")
    
    cmd.extend(["--service", service_name])
    # cmd.append("--skip-deploys") # Use this to avoid multiple deploys, trigger one at end manually if needed.
    
    print(f"Running command for {service_name} with {len(vars_dict)} variables...")
    try:
        subprocess.run(cmd, check=True)
        print(f"Success for {service_name}")
    except subprocess.CalledProcessError as e:
        print(f"Error setting variables for {service_name}: {e}")

if __name__ == "__main__":
    # Backend
    backend_vars = parse_env_file("backend/.env")
    if backend_vars:
        set_vars("backend", backend_vars)
    
    # Frontend
    frontend_vars = parse_env_file("frontend/.env")
    if frontend_vars:
        set_vars("frontend", frontend_vars)
