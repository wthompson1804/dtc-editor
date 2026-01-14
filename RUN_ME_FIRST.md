# DTC Editor Pilot — Start Here (Mac)

You only do setup **once**.

## Step 1 — Open Terminal
1. Press **Command + Space**
2. Type: `Terminal`
3. Press **Enter**

## Step 2 — Go to the project folder
1. Type `cd ` (c-d then a space)
2. Drag the DTC Editor folder from Finder into the Terminal window
3. Press **Enter**

## Step 3 — Run the installer (one command)
Copy/paste this and press Enter:

./setup_mac.sh

### If macOS blocks it (“unidentified developer”)
1. Open **System Settings → Privacy & Security**
2. Scroll down to **Security**
3. Click **Allow Anyway** for `setup_mac.sh`
4. Run `./setup_mac.sh` again

## Step 4 — Run the editor (from now on)
1. Double-click **run_editor.command**
2. Drag your `.docx` file into the window
3. Press **Enter**
4. Your outputs are in the `dtc_out/` folder:
   - `*.clean.docx`
   - `*.redline.docx`
   - `*.changelog.json`
   - `*.changelog.txt`

That’s it.
