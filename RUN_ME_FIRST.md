# DTC Editor Setup Guide (Mac)

This guide will walk you through setting up the DTC Editor step by step. **You only need to do this once.**

---

## Before You Start

You need two things installed on your Mac:

### 1. Python 3.10 or newer

**Check if you have it:**
1. Open **Terminal** (press `Command + Space`, type `Terminal`, press Enter)
2. Type: `python3 --version` and press Enter
3. If you see `Python 3.10` or higher, you're good!

**If you don't have Python or it's too old:**
1. Go to: https://www.python.org/downloads/
2. Click the big yellow "Download Python" button
3. Open the downloaded file and follow the installer
4. Restart Terminal after installing

### 2. Homebrew (for installing Vale)

**Check if you have it:**
1. In Terminal, type: `brew --version` and press Enter
2. If you see a version number, you're good!

**If you don't have Homebrew:**
1. Go to: https://brew.sh
2. Copy the command shown on that page (starts with `/bin/bash -c`)
3. Paste it into Terminal and press Enter
4. Follow the prompts (you'll need to enter your Mac password)
5. **Important:** After it finishes, it will show you two commands to run. Run them both!

---

## Setup Steps

### Step 1: Open Terminal and go to the project folder

1. Open **Terminal** (press `Command + Space`, type `Terminal`, press Enter)
2. Type `cd ` (the letters c-d, then a space)
3. Open Finder and drag the **dtc_editor_pilot_final** folder into the Terminal window
4. Press **Enter**

Your Terminal should now show something like:
```
your-mac:dtc_editor_pilot_final yourname$
```

### Step 2: Run the setup script

Copy and paste this command, then press Enter:

```
./setup_mac.sh
```

**If you see "permission denied":**
```
chmod +x setup_mac.sh && ./setup_mac.sh
```

**If macOS says "unidentified developer":**
1. Open **System Settings** (click Apple menu > System Settings)
2. Click **Privacy & Security** in the sidebar
3. Scroll down to the **Security** section
4. You'll see a message about `setup_mac.sh` being blocked
5. Click **Allow Anyway**
6. Go back to Terminal and run `./setup_mac.sh` again

The setup will take a few minutes. Wait until you see "Setup complete!"

### Step 3: Get an Anthropic API Key

The editor uses Claude AI, which requires an API key.

1. Go to: https://console.anthropic.com/
2. Create an account or sign in
3. Click on **API Keys** in the sidebar
4. Click **Create Key**
5. Give it a name like "DTC Editor"
6. Copy the key (it starts with `sk-ant-`)
7. **Save this key somewhere safe** - you'll need it every time you use the app

**Note:** Anthropic charges for API usage. Check their pricing at https://www.anthropic.com/pricing

---

## Running the Editor

After setup is complete, here's how to run the editor:

### Step 1: Open Terminal and go to the project folder

(Same as Setup Step 1)

1. Open **Terminal**
2. Type `cd ` then drag the project folder into Terminal
3. Press **Enter**

### Step 2: Activate the virtual environment

Copy and paste this command:

```
source .venv/bin/activate
```

You should see `(.venv)` appear at the start of your Terminal prompt.

### Step 3: Start the app

Copy and paste this command:

```
python3 -m streamlit run app.py
```

**First time only:** Streamlit will ask for your email. Just press Enter to skip.

### Step 4: Use the app

1. Your web browser will open automatically to `http://localhost:8501`
2. Paste your Anthropic API key in the "Anthropic API Key" field
3. Drag and drop a `.docx` file onto the upload area
4. Click "Process Document"
5. Wait for processing (this can take a few minutes for large documents)
6. Download your edited files when done

### Step 5: When you're done

Press `Control + C` in Terminal to stop the app.

---

## Quick Start (After Setup)

Once you've done the initial setup, you can start the editor with these commands:

```
cd ~/Downloads/dtc_editor_pilot_final
source .venv/bin/activate
python3 -m streamlit run app.py
```

---

## Troubleshooting

### "command not found: python3"
You need to install Python. See "Before You Start" above.

### "No module named streamlit"
The setup didn't complete properly. Run `./setup_mac.sh` again.

### "No module named dtc_editor"
Make sure you activated the virtual environment: `source .venv/bin/activate`

### The browser doesn't open
Manually go to: http://localhost:8501

### "Connection refused" in browser
The app isn't running. Make sure you ran `python3 -m streamlit run app.py`

### API key errors
Make sure you copied the full API key (starts with `sk-ant-`)

---

## Getting Help

If you run into problems, contact the person who gave you this software.
