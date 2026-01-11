# Download Facebook Photos
This script will download all publicly availible photos from any public facebook account or private ones if you have them added as friends.

This script is a fork from https://github.com/tonyflo/facebook-download-photos, the whole script is just modifications of his script.

I have added some features and quality of life changes.
First change is that I have divided it into 2 phases, Indexing and Downloading.

# Indexing
Indexes both albums automatically:
photos_of and
photos_by

# Uses two-phase indexing:
1.Collects all fbids via scrolling

2.Visits each photo page individually

# Extracts:
Photo ID (fbid)
Creation timestamp (actual photo date)
Highest-quality image URL

Stores everything in a SQLite database:
path: "photos/<username>/.index.db"

# Download features
*Downloads photos outside Selenium*
Uses Facebook CDN URLs directly
Parallel downloads [default: 3 threads]
Automatic retries [2 attempts]
Skips already downloaded & verified files

# Added Multi-user support
Each user has:
Separate folders
Separate database
The path will be photos/(username)

# SQLite index tracker
Download status
SHA-256 hash

# *Quality-of-life*
Clear status messages:
--> Login
--> Album discovery
--> Index and Download progress with bar
--> Headless Chrome is used
# FOLDER STURCTURE 
```sh
photos/
├── username1/
│   ├── of/
│   │   ├── 20201225_fb_of_username1_123456789.jpg
│   ├── by/
│   │   ├── 20190514_fb_by_username1_987654321.jpg
│   └── .index.db
├── username2/
│   ├── of/
│   ├── by/
│   └── .index.db
```

# Filename format
YYYYMMDD_fb_<album>_<username>_<fbid>.jpg

# REMOVED
Removed -a

## How to Download Photos from Facebook

**NOTE:** You will need to have **Python 3.11 or newer**, **Google Chrome** ( the base script was hard coded for google chrome only ), and optionally **git** installed.

This code was tested on Windows 11, but should also work on any OS.
 
### 1. Clone or download this repository
```sh
git clone https://github.com/GitBulbasaur/facebook-download-photos.git
cd facebook-download-photos
```

### 2.Install required dependencies
```sh
pip install selenium webdriver-manager tqdm pillow
```

### 3. Download Facebook photos from a single user.
Execute the following command to download all Facebook photos from a single user.
```sh
python download.py -e you@example.com -p password -username
```
**NOTE:** If you do not use --index-only or --download-only both indexing and downloading will be done one after another. ( check command overview for more details )
**NOTE:** *Be sure to replace *username*, *email* and *password* with your actual Facebook username, email, and password.*

### 4. Mass/Bulk Download Facebook photos from many users.

# Make a user list
Make a .txt file with all users name in it like, comments and blank spaces are allowed and should not cause any issues.
username1
username2
username3

Name it anything you like.
# USE --users-file argument instead of -u or -username

# Execute the following command to download all Facebook photos from many users.
```sh
python download.py -e you@example.com -p password --users-file "path to the file"
```
**NOTE:** If you do not use --index-only or --download-only both indexing and downloading will be done one after another. ( check command overview for more details )
**NOTE:** *Be sure to replace *email* and *password* with your actual Facebook email, and password.*
### WARNING: DO NOT RUN MULTIPLE INSTANCES ON SAME ACCOUNT

## Command Overview
```
usage: download.py [-h] -e EMAIL -p PASSWORD {[-u USERNAME] or [--users-file USERS_FILE]} {[--index-only] or [--download-only] or nothing}

options:
  -h, --help 
  -e, --email EMAIL
  -p, --password PASSWORD
User selection (choose one)
  -u, --username USERNAME
  --users-file USERS_FILE
Execution modes ( default is index+download )
  --index-only Indexes photos but does not download.
  --download-only Downloads photos using the existing index.
```
