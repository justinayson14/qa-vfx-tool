# qa-vfx-tool

This tool is a command-line utility designed to streamline the QA process for VFX shots. It processes data from Baselight and Xytech files, correlates it with a video file, and generates several outputs to aid in the review process.

The script can:

- Parse and upload Baselight and Xytech data to a MongoDB database.
- Identify frame ranges from Baselight data that correspond to a given video file.
- Generate an Excel report (`output.xlsx`) containing shot locations, frame ranges, timecode ranges, and embedded thumbnails for each shot.
- Render short video clips for each identified frame range.
- Upload the rendered clips to Vimeo for easy review.
- Generate a CSV report (`unused_frames.csv`) of frames that are outside the video's duration.

## Prerequisites

Before running the script, you need to have the following installed:

- Python 3
- `ffmpeg` (must be installed on your system and accessible from the command line)
- A MongoDB Atlas account and cluster.
- A Vimeo account with API credentials for an app.

## Setup

1. **Clone the repository:**

   ```bash
   git clone <repository-url>
   cd qa-vfx-tool
   ```

2. **Install Python dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

   *(Note: A `requirements.txt` file would be ideal. If one is not present, install the packages manually)*

   ```bash
   pip install ffmpeg-python openpyxl pymongo pandas python-vimeo python-dotenv
   ```

3. **Create a `.env` file:**
   Create a file named `.env` in the root directory of the project and add your credentials. The script uses this file to connect to MongoDB and Vimeo.

   ```env
   # MongoDB Credentials
   MONGODB_USER="your_mongodb_username"
   MONGODB_PASS="your_mongodb_password"

   # Vimeo API Credentials
   ACCESS_TOKEN="your_vimeo_access_token"
   CLIENT_ID="your_vimeo_client_id"
   CLIENT_SECRET="your_vimeo_client_secret"
   ```

## How to Run

The script is run from the command line and accepts several arguments to perform different tasks.

### 1. Uploading Data to MongoDB

To process and upload the `baselight.txt` and `xytech.txt` files to your MongoDB database, run:

```bash
python qa_to_vfx.py --baselight /path/to/baselight.txt --xytech /path/to/xytech.txt
```

This will drop the existing `baselight` and `xytech` collections and populate them with the new data.

### 2. Processing a Video and Generating Outputs

To process a video file against the data in the database and generate all outputs (Excel report, thumbnails, Vimeo uploads, and unused frames CSV), use the `--process` and `--output` flags.

```bash
python qa_to_vfx.py --process /path/to/video.mp4 --output
```

This command will:

1. Find all frame ranges from the Baselight data that are within the duration of `video.mp4`.
2. Match them to the correct Xytech locations.
3. Create `output.xlsx` with details and thumbnails.
4. Create a `videos/` directory with short clips for each range.
5. Upload those clips to your Vimeo account.
6. Create `unused_frames.csv` for your reference.

### All-in-One Command

You can also perform all steps in a single command:

```bash
python qa_to_vfx.py --baselight /path/to/baselight.txt --xytech /path/to/xytech.txt --process /path/to/video.mp4 --output
```
