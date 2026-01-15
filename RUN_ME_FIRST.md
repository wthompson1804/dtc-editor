# DTC Editor Setup Guide (Mac)

This guide will walk you through setting up the DTC Editor step by step. **You only need to do this once.**

**Total time: 10-15 minutes**

---

## Step 1: Open Terminal

Terminal is the command-line app on your Mac. Here's how to open it:

1. Press **Command + Space** (this opens Spotlight search)
2. Type **Terminal**
3. Press **Enter**

A window with a black or white background will open. This is Terminal.

**Keep Terminal open for all the following steps.**

---

## Step 2: Check if You Have Python

Copy this command, paste it into Terminal, and press **Enter**:

```
python3 --version
```

**What you should see:**
- `Python 3.10.x` or `Python 3.11.x` or `Python 3.12.x` or higher = You're good! Skip to Step 3.
- `command not found` or `Python 3.9.x` or lower = You need to install Python. See below.

### Installing Python (only if needed)

1. Open Safari and go to: **https://www.python.org/downloads/**
2. Click the big yellow **"Download Python 3.x.x"** button
3. Open your **Downloads** folder and double-click the file (named like `python-3.12.x-macos.pkg`)
4. Click through the installer (just keep clicking **Continue** and **Agree**)
5. When done, **close Terminal completely** (Command + Q)
6. **Re-open Terminal** (Command + Space, type Terminal, press Enter)
7. Run `python3 --version` again to verify it worked

---

## Step 3: Check if You Have Homebrew

Copy this command, paste it into Terminal, and press **Enter**:

```
brew --version
```

**What you should see:**
- `Homebrew 4.x.x` = You're good! Skip to Step 4.
- `command not found: brew` = You need to install Homebrew. See below.

### Installing Homebrew (only if needed)

1. Copy this entire command (it's long - make sure you get all of it):

```
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

2. Paste it into Terminal and press **Enter**
3. When prompted, **enter your Mac password** (you won't see the characters as you type - this is normal)
4. Press **Enter** when it asks you to confirm
5. **Wait** - this takes 5-10 minutes
6. **IMPORTANT:** When it finishes, look for lines that say "Next steps" or "Run these commands". Copy and run each command it shows you.

Usually it tells you to run something like:
```
echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
eval "$(/opt/homebrew/bin/brew shellenv)"
```

7. Verify it worked by running `brew --version` again

---

## Step 4: Download the DTC Editor

Copy this command, paste it into Terminal, and press **Enter**:

```
cd ~/Downloads && git clone https://github.com/wthompson1804/dtc-editor.git
```

**What this does:** Downloads the DTC Editor to your Downloads folder.

**If you see "git: command not found":**
1. Run: `xcode-select --install`
2. Click **Install** in the popup
3. Wait for it to finish (5-10 minutes)
4. Try the download command again

---

## Step 5: Go to the Project Folder

Copy this command, paste it into Terminal, and press **Enter**:

```
cd ~/Downloads/dtc-editor
```

Your Terminal prompt should now show `dtc-editor` somewhere in it.

---

## Step 6: Run the Setup Script

Copy this command, paste it into Terminal, and press **Enter**:

```
chmod +x setup_mac.sh && ./setup_mac.sh
```

**What happens:**
- The script installs Vale (a writing style checker)
- Creates a Python virtual environment
- Installs all required packages

**Wait for it to finish.** You'll see "Setup complete!" when done.

### If You See Errors:

**"permission denied"** - The chmod command above should fix this. If not, try:
```
bash setup_mac.sh
```

**"unidentified developer" popup** -
1. Open **System Settings** (click Apple menu at top-left > System Settings)
2. Click **Privacy & Security** in the left sidebar
3. Scroll down and find a message about `setup_mac.sh` being blocked
4. Click **Allow Anyway**
5. Go back to Terminal and run the command again

---

## Step 7: Get an Anthropic API Key

The editor uses Claude AI to rewrite your documents. You need an API key.

1. Open Safari and go to: **https://console.anthropic.com/**
2. Click **Sign Up** and create an account (or sign in if you have one)
3. Once logged in, click **API Keys** in the left sidebar
4. Click **Create Key**
5. Name it something like `DTC Editor`
6. Click **Create Key**
7. **IMPORTANT:** Copy the key immediately! It starts with `sk-ant-api03-...`
8. Save it somewhere safe (like in Notes app) - you'll need it every time

**Note:** Anthropic charges ~$0.50-1.00 per document processed. They require a credit card.

---

## Step 8: Start the Editor

Copy these commands, paste them into Terminal, and press **Enter**:

```
source .venv/bin/activate
streamlit run app.py
```

**First time only:** If Streamlit asks for your email, just press **Enter** to skip.

**What happens:**
- Your web browser opens automatically
- You'll see the DTC Editor interface

**If your browser doesn't open automatically:**
Open Safari and go to: **http://localhost:8501**

---

## Step 9: Use the Editor

1. **Paste your API key** in the "Anthropic API Key" field
2. **Drag and drop** a Word document (.docx) onto the upload area
3. Click **"Process Document"**
4. **Wait** - processing takes 2-10 minutes depending on document size
5. **Keep your Mac awake** - don't let the screen sleep!
6. When done, click the download buttons to get your edited files

### Output Files:
- **Clean Document** - Your edited document with all changes applied
- **Redline** - Shows all changes with track changes
- **Change Log** - Detailed list of every edit made

---

## Step 10: Stop the Editor

When you're done, go back to Terminal and press **Control + C** to stop the app.

---

# Quick Start (For Next Time)

After the initial setup, starting the editor is simple. Open Terminal and run:

```
cd ~/Downloads/dtc-editor
source .venv/bin/activate
streamlit run app.py
```

Or copy this one-liner:
```
cd ~/Downloads/dtc-editor && source .venv/bin/activate && streamlit run app.py
```

---

# Troubleshooting

## "command not found: python3"
You need to install Python. Go back to Step 2.

## "command not found: brew"
You need to install Homebrew. Go back to Step 3.

## "No module named streamlit"
Run the setup script again:
```
cd ~/Downloads/dtc-editor
./setup_mac.sh
```

## "No module named dtc_editor"
You forgot to activate the virtual environment. Run:
```
source .venv/bin/activate
```

## Browser shows "This site can't be reached"
The app isn't running. Make sure you ran `streamlit run app.py` and saw the "You can now view your Streamlit app" message.

## "Invalid API key"
Make sure you copied the entire key. It should start with `sk-ant-api03-` and be very long.

## Processing stops when screen goes dark
Your Mac went to sleep. Before processing:
1. Go to **System Settings > Lock Screen**
2. Set "Turn display off" to **Never** (or a long time)
3. Or run this command before processing: `caffeinate -d &`

## "Rate limit error"
You're processing too fast. Wait a minute and try again, or use a smaller document.

---

# Getting Help

If you run into problems:
1. Take a screenshot of the error
2. Copy any red error text from Terminal
3. Send both to the person who shared this tool with you
