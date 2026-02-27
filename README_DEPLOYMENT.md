# GCP Deployment Guide

## Server Specifications
- **Instance Type:** GCP e2-micro
- **RAM:** 1GB + 2GB Swap
- **Disk:** 30GB
- **OS:** Debian/Ubuntu Linux

## Prerequisites

1. **Enable Swap Space (Critical for 1GB RAM):**
```bash
# Check if swap exists
swapon --show

# If no swap, create 2GB swap file
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# Make permanent (add to /etc/fstab)
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

2. **Install Podman:**
```bash
sudo apt update
sudo apt install -y podman
```

3. **Install Git:**
```bash
sudo apt install -y git
```

## Deployment Steps

### 1. Clone Repository
```bash
cd ~
git clone https://github.com/ryanlwk/telegrambot_marksix_calculation.git
cd telegrambot_marksix_calculation
```

### 2. Configure Environment
```bash
# Copy sample and edit
cp env.sample .env
nano .env

# Required variables:
# TELEGRAM_BOT_TOKEN=your_bot_token
# TARGET_CHAT_ID=your_chat_id
# OPENROUTER_API_KEY=your_openrouter_key
# LANGFUSE_SECRET_KEY=your_langfuse_secret
# LANGFUSE_PUBLIC_KEY=your_langfuse_public
# LANGFUSE_BASE_URL=https://us.cloud.langfuse.com
```

### 3. Create Required Directories
```bash
mkdir -p charts temp_images
```

### 4. Build Container
```bash
podman build -t mark-six-bot .
```

### 5. Run Container
```bash
podman run -d \
  --name mark-six-bot \
  --restart unless-stopped \
  --env-file .env \
  --memory=850m \
  --memory-reservation=512m \
  -v ./history.csv:/app/history.csv:Z \
  -v ./charts:/app/charts:Z \
  -v ./temp_images:/app/temp_images:Z \
  mark-six-bot
```

**Note:** The `:Z` flag is important for SELinux systems (relabels files for container access).

### 6. Verify Running
```bash
# Check container status
podman ps

# View logs
podman logs -f mark-six-bot

# Expected output:
# - "Langfuse client is authenticated and ready!"
# - "Fetching latest Mark Six data on startup..."
# - "Startup: history.csv updated successfully"
# - "Bot started with scheduled job (Daily at 21:35 HKT / 9:35 PM)"
```

## Monitoring & Maintenance

### Memory Monitoring
```bash
# Real-time container stats
podman stats mark-six-bot

# Check system memory and swap
free -h

# Check if swap is being used
swapon --show
```

### Log Management
```bash
# View recent logs
podman logs --tail 100 mark-six-bot

# Follow logs in real-time
podman logs -f mark-six-bot

# Check log file size (should auto-rotate at 10MB)
podman inspect mark-six-bot | grep -A 10 LogConfig
```

### Container Management
```bash
# Stop bot
podman stop mark-six-bot

# Start bot
podman start mark-six-bot

# Restart bot (applies code changes after git pull)
podman restart mark-six-bot

# Remove container (for rebuild)
podman rm -f mark-six-bot

# View container health status
podman ps --format "{{.Names}} {{.Status}}"
```

## Updating the Bot

### Pull Latest Code
```bash
cd ~/telegrambot_marksix_calculation
git pull origin main
```

### Rebuild and Restart
```bash
# Stop and remove old container
podman stop mark-six-bot
podman rm mark-six-bot

# Rebuild image with new code
podman build -t mark-six-bot .

# Run new container
podman run -d \
  --name mark-six-bot \
  --restart unless-stopped \
  --env-file .env \
  --memory=850m \
  --memory-reservation=512m \
  -v ./history.csv:/app/history.csv:Z \
  -v ./charts:/app/charts:Z \
  -v ./temp_images:/app/temp_images:Z \
  mark-six-bot
```

## Troubleshooting

### Bot Not Starting
```bash
# Check logs for errors
podman logs mark-six-bot

# Common issues:
# - Missing .env variables → Check .env file
# - Out of memory → Check swap is enabled
# - Port conflicts → Check no other bots running
```

### Out of Memory (OOM)
```bash
# Check if swap is active
swapon --show

# Check memory usage
free -h

# If OOM persists, reduce memory limit
podman run ... --memory=700m --memory-reservation=400m ...
```

### Health Check Failing
```bash
# Check if process is running
podman exec mark-six-bot pgrep -f python

# If no output, bot crashed - check logs
podman logs --tail 50 mark-six-bot
```

### Scheduled Job Not Running
```bash
# Check logs around 21:35 HKT
podman logs mark-six-bot | grep "21:35"

# Verify timezone is correct
podman exec mark-six-bot date
```

## Performance Optimization

### Reduce Memory Usage Further
If experiencing OOM issues:

1. **Reduce chart DPI** (in `agent_setup.py`):
   - Change `dpi=100` to `dpi=80`

2. **Limit historical data**:
   - Keep only last 6 months in `history.csv`

3. **Adjust memory limits**:
   - Try `--memory=700m --memory-reservation=400m`

## Security Best Practices

- ✅ Never commit `.env` file to git
- ✅ Rotate API keys regularly
- ✅ Monitor logs for suspicious activity
- ✅ Keep system packages updated: `sudo apt update && sudo apt upgrade`
- ✅ Use firewall: Only allow SSH (22) and outbound HTTPS (443)

## Backup

### Backup Important Files
```bash
# Backup history.csv and charts
tar -czf backup-$(date +%Y%m%d).tar.gz history.csv charts/

# Copy to safe location
scp backup-*.tar.gz user@backup-server:/backups/
```

## Auto-start on System Boot

### Enable Podman Service
```bash
# Generate systemd service
podman generate systemd --name mark-six-bot --files --new

# Move to systemd directory
sudo mv container-mark-six-bot.service /etc/systemd/system/

# Enable auto-start
sudo systemctl enable container-mark-six-bot.service
sudo systemctl start container-mark-six-bot.service

# Check status
sudo systemctl status container-mark-six-bot.service
```

## Support

For issues or questions, check:
- GitHub Issues: https://github.com/ryanlwk/telegrambot_marksix_calculation/issues
- Logs: `podman logs mark-six-bot`
- Security Audit: See `SECURITY_AUDIT.md`

---

**Last Updated:** 2026-02-26  
**Tested On:** GCP e2-micro (1GB RAM + 2GB Swap)
