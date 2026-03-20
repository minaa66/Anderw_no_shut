# 🌐 Network Configuration Manager

A Python-based utility for safely backing up, editing, and restoring Cisco network device configurations. This tool supports SSH, SCP, and TFTP transfer methods for comprehensive network device management.

## ⚡ Overview

The **Network Configuration Manager** is designed to help network administrators safely modify Cisco switch and router configurations with automatic backup and restore capabilities. It provides a seamless workflow for:

- Backing up device configurations before making changes
- Editing configurations in your preferred text editor
- Restoring modified configurations with multiple transfer method fallbacks
- Applying changes immediately without device restart

## ✨ Key Features

### 🔐 Safe Configuration Management
- **Automatic backups** before any modifications
- **Configuration validation** before and after changes
- **Multiple restore methods** with intelligent fallback
- **Session logging** for audit trails

### 📡 Multi-Protocol Support
- **SSH/Netmiko**: Primary SSH connection method for Cisco devices
- **SCP (Secure Copy)**: Fast secure file transfer protocol
- **TFTP**: Traditional high-speed TFTP transfer method
- **Direct Configuration**: Line-by-line configuration as fallback

### 🎯 Device Support
- Cisco IOS (Standard)
- Cisco IOS XE (Catalyst)
- Cisco IOS XR (ASR)
- Cisco NX-OS (Nexus)
- **Auto-detection** of device type

### 🛡️ Safety Features
- IP address validation
- Device connectivity verification (ping check)
- Configuration register checking
- SCP server security (automatic enable/disable)
- Connection retry logic (3 attempts)
- Configuration verification after restore

### 📊 Configuration Features
- Hostname-based filename generation
- Timestamped backups
- Configuration file staging area
- Organized backup directory structure
- Cross-platform support (Windows/Linux/macOS)

## 📋 Prerequisites

### System Requirements
- Python 3.6 or higher
- Network connectivity to Cisco devices
- SSH/SCP enabled on target devices
- (Optional) TFTP server for faster transfers
