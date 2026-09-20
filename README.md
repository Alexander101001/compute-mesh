# Compute Mesh — $0/forever infrastructure
- 📱 Phone (controller): Termux, schedules, tunnels
- ☁️ Oracle Micro VM (92.5.18.80): 24/7 node agent (jobs/pending/*.sh)
- 🧠 Oracle A1 4CPU/24GB: auto-provisioning via phone retry loop
- ⚡ GitHub Actions: overflow compute + healthchecks
- 🤗 HF Space: public status dashboard
- 🟩 Kaggle/Colab: GPU spot jobs (artifact → Drive/HF)

## Run a job on a VM
Push `jobs/pending/myjob.sh` — the node agent picks it up in <60s.
