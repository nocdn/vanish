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
2. Click on your profile icon in the top right corner, and select `Profile`.
3. On the left sidebar, select `API Tokens`
4. Under "API Tokens", press `create token`
5. Scroll down, and under "Custom token", press `Get started`
6. Give the token a name (eg. cloudflare-temp-mail)
7. Under "Permissions", select `Zone` then `Email Routing Rules` then `Edit`
8. For the "Zone Resources, select `Include`, then `Specific Zone`, then the domain you have.
9. Press continue to summary, and copy the token.

To get your Cloudflare Zone ID:

1. Go to your [Cloudflare dashboard](https://dash.cloudflare.com)
2. Under domain names, find the domain you want to use
3. Select it's 3-dot menu, scroll down and press `Copy zone ID`

> [!important]
> You will most likely need to verify your email address first with cloudflare to allow routing to it.
>
> This verification email should be sent after creating your first temporary email address.

Build the Docker image:

```bash
docker build -t cloudflare-temp-mail .
```

Run the Docker container:

```bash
docker run -d -p 6020:6020 --env-file .env --rm --name cloudflare-temp-email cloudflare-temp-mail
```

The API should now be running on port `6020`

To access the API, you can use the following curl command:

```bash
curl http://localhost:6020/generate
```

To list the emails, you can use the following curl command:

```bash
curl http://localhost:6020/list
```

### Installation for local development

##### Prerequisites

- Python 3.10+

Clone the repository and navigate to the directory:

```bash
git clone https://github.com/nocdn/cloudflare-temp-email.git
cd cloudflare-temp-mail/
```

Fill out the .env file by copying the .env.example file:

```bash
cp .env.example .env
```

Fill in the .env file with your Cloudflare API token, zone id, domain name, and destination email address. For instructions on how to get the api token and zone id, see above.

Create a virtual environment and install the dependencies:

```bash
python -m venv venv
source venv/bin/activate  # on Windows use `venv\Scripts\activate`
pip install -r requirements.txt
```

Run the api:

```bash
python app.py
```

### License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
