# CyberLion Telegram File Stream Bot

## Overview
This is a Telegram bot that streams files directly from Telegram to a web link. It allows users to generate direct download links for files sent to the bot.

## Project Structure
- `Adarsh/` - Main application package
  - `__main__.py` - Application entry point
  - `vars.py` - Configuration variables loaded from environment
  - `bot/` - Telegram bot related code
    - `__init__.py` - StreamBot client initialization
    - `clients.py` - Multi-client support
    - `plugins/` - Bot command handlers (admin, start_help, stream, extra)
  - `server/` - Web server for file streaming
    - `__init__.py` - Web server setup
    - `stream_routes.py` - HTTP routes for streaming
  - `template/` - HTML templates for download pages
  - `utils/` - Utility functions (database, file handling, etc.)

## Running the Application
```bash
python -m Adarsh
```

## Required Environment Variables
- `API_ID` - Telegram API ID (from my.telegram.org)
- `API_HASH` - Telegram API Hash (from my.telegram.org)
- `BOT_TOKEN` - Telegram Bot Token (from @BotFather)
- `BIN_CHANNEL` - Telegram channel ID for storing files
- `DATABASE_URL` - MongoDB connection URL
- `OWNER_USERNAME` - Bot owner's Telegram username

## Optional Environment Variables
- `SESSION_NAME` - Bot session name (default: filetolinkbot)
- `WORKERS` - Number of workers (default: 4)
- `PORT` - Web server port (default: 5000)
- `FQDN` - Fully Qualified Domain Name for file links
- `OWNER_ID` - Owner Telegram user IDs (space separated)
- `UPDATES_CHANNEL` - Updates channel username

## Tech Stack
- Python 3.11
- Pyrogram - Telegram MTProto API client
- aiohttp - Async HTTP server
- Motor - Async MongoDB driver
- MongoDB - Database for user/file data

## Recent Changes
- Initial Replit environment setup
- Updated port to 5000 for Replit compatibility
- Added default values for environment variables
