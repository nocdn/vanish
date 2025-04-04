# cloudflare-temp-mail

> self-hosted REST API (with frontend) to automatically create a temporary email address on your own domain using cloudflare

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

### Usage with Docker (recommended)

##### Prerequisites

- [Docker](https://www.docker.com/)

Clone the repository and navigate to the directory:

```bash
git clone https://github.com/nocdn/cloudflare-temp-mail.git
cd cloudflare-temp-mail/
```

Copy the `.env.example` file to `.env`:

```bash
cp .env.example .env
```

Fill in the .env file with your Cloudflare API token, zone id, domain name, and destination email address

To get your Cloudflare API token:

1. Go to your [Cloudflare dashboard](https://dash.cloudflare.com)
2. Click on your profile icon in the top right corner, and select "Profile".
3. On the left sidebar, select "API Tokens".
4. Under "API Tokens", press "create token"
5. Scroll down, and under "custom token", press "Get started"
6. Give the token a name (eg. cloudflare-temp-mail)
7.

Build the and run the Docker image:

```bash
docker compose up -d --build
```

(the `-d` flag runs the container in detached mode, and the `--build` flag rebuilds the image if there are any changes)

There now should be a frontend running at port `6030`, and the API running at port `7070`.

To access the API, you can use the following curl command:

```bash
curl -F "file=@audio.mp3" -OJ http://localhost:7070/process
```

(replace `audio.mp3` with the path to your audio file, the -OJ flag will save the file with the returned name with the \_edited suffix)

### Installation for local development

##### Prerequisites

- Python 3.10+

Clone the repository and navigate to the directory:

```bash
git clone https://github.com/nocdn/ad-segment-trimmer.git
cd ad-segment-trimmer/
```

Fill out the .env file by copying the .env.example file:

```bash
cp .env.example .env
```

1. Make sure you have an Gemini API key, as an environment variable called `GEMINI_API_KEY` in the `.env` file.
2. Make sure you have a Fireworks AI API key, as an environment variable called `FIREWORKS_API_KEY` in the `.env` file.
3. Set any rate limits you want in the `.env` file (optional).

##### backend

Install the dependencies:

```bash
cd backend
pip install -r requirements.txt
```

Run the backend:

```bash
python app.py
```

##### frontend

Install the dependencies:

```bash
cd frontend
npm install
```

Run the frontend:

```bash
npm run dev
```

### License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
