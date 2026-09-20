#!/data/data/com.termux/files/usr/bin/sh
# Auto-provision Oracle Micro VM once SSH is reachable. Idempotent. Safe to re-run.
HOME=/data/data/com.termux/files/home
KEY=$HOME/.ssh/oci_vm_key
IP=92.5.18.80
LOG=$HOME/compute-mesh/logs/provision.log
mkdir -p $HOME/compute-mesh/logs
exec >>$LOG 2>&1
echo "=== provision attempt $(date -u) ==="

SSH="ssh -i $KEY -o StrictHostKeyChecking=no -o ConnectTimeout=20"
SCP="scp -i $KEY -o StrictHostKeyChecking=no -o ConnectTimeout=20"

# wait for ssh (up to 40 min)
for i in $(seq 1 60); do
  if $SSH -o ConnectTimeout=30 opc@$IP 'echo ALIVE' 2>/dev/null | grep -q ALIVE; then break; fi
  echo "ssh not ready (try $i)"; sleep 40
done
$SSH opc@$IP 'echo ALIVE' | grep -q ALIVE || { echo "giving up this round"; exit 1; }

# packages (skip if done)
$SSH opc@$IP 'which git tmux >/dev/null 2>&1 || sudo dnf -qy install git tmux'
# deploy key + add to github
$SSH opc@$IP '[ -f ~/.ssh/mesh_deploy_key ] || ssh-keygen -q -t ed25519 -N "" -f ~/.ssh/mesh_deploy_key'
PUB=$($SSH opc@$IP 'cat ~/.ssh/mesh_deploy_key.pub')
gh -R Alexander101001/compute-mesh api repos/:owner/:repo/keys --jq .[].key 2>/dev/null | grep -q "${PUB##* }" \
  || gh -R Alexander101001/compute-mesh api repos/:owner/:repo/keys -f title=mesh-micro-vm -f key="$PUB" 2>/dev/null
# clone repo
$SSH opc@$IP 'GIT_SSH_COMMAND="ssh -i ~/.ssh/mesh_deploy_key -o StrictHostKeyChecking=no" \
  bash -c "[ -d ~/compute-mesh/.git ] || git clone git@github.com:Alexander101001/compute-mesh.git ~/compute-mesh"'
# systemd service
BOT=$(cat $HOME/.credentials/telegram/bot_token)
$SSH opc@$IP "sudo tee /etc/systemd/system/mesh-node.service >/dev/null <<EOF
[Unit]
Description=Compute mesh node agent
After=network-online.target
[Service]
User=opc
Environment=MESH_BOT_ENV=1
ExecStart=/bin/bash -c 'MESH_TOKEN=$BOT MESH_ADMIN=890601506 MESH_REPO=/home/opc/compute-mesh /usr/bin/python3 /home/opc/compute-mesh/node_agent.py'
Restart=always
RestartSec=30
[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload && sudo systemctl enable --now mesh-node && sudo systemctl is-active mesh-node"
echo "=== provision done $(date -u) ==="
