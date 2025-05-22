# cloudflare-temp-mail

> self-hosted REST API to automatically create temporary email addresses on your own domain using Cloudflare, with optional expiry.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

This API allows you to quickly generate temporary email forwarding rules on your Cloudflare-managed domain. You can optionally set an expiry time (minimum 5 minutes), after which the email rule will be automatically deleted by a background cleanup job.

### Deployment with Docker (Recommended)

##### Prerequisites

- [Docker](https://www.docker.com/) installed.
- A domain name managed by Cloudflare.
- Cloudflare Email Routing configured and enabled for your domain.

##### Setup Steps

1.  **Clone the repository** and navigate into the directory:

    ```bash
    git clone https://github.com/nocdn/cloudflare-temp-mail.git
    cd cloudflare-temp-mail/
    ```

2.  **Create the `.env` file**:
    Copy the example file:

    ```bash
    cp .env.example .env
    ```

    Edit the `.env` file and fill in your details:

    - `CLOUDFLARE_API_TOKEN`: Your Cloudflare API Token (see instructions below).
    - `CLOUDFLARE_ZONE_ID`: Your Cloudflare Zone ID for the domain (see instructions below).
    - `DOMAIN_NAME`: The domain you own and want to use to create the temporary addresses on (e.g., `example.com`).
    - `DESTINATION_EMAIL`: The real email address where temporary emails should be forwarded.
    - _(Optional)_ `FLASK_DEBUG` and `FLASK_RUN_PORT` if you need to change defaults.

3.  **Get Cloudflare Credentials**:

    - **API Token (`CLOUDFLARE_API_TOKEN`)**:
      1.  Go to your [Cloudflare dashboard](https://dash.cloudflare.com) -> My Profile -> API Tokens.
      2.  Click **"Create Token"**.
      3.  Find the **"Custom token"** template and click **"Get started"**.
      4.  Give the token a name (e.g., `temp-email-api`).
      5.  Set the following **Permissions**:
          - `Zone` - `Email Routing` - `Edit`
      6.  Set the **Zone Resources**:
          - `Include` - `Specific Zone` - Select your `DOMAIN_NAME`.
      7.  Click **"Continue to summary"**, then **"Create Token"**.
      8.  **Copy the generated token immediately** and paste it into your `.env` file. You won't see it again.
    - **Zone ID (`CLOUDFLARE_ZONE_ID`)**:
      1.  Go to your [Cloudflare dashboard](https://dash.cloudflare.com).
      2.  Select your `DOMAIN_NAME`.
      3.  On the **Overview** page for the domain, find the **"Zone ID"** on the right-hand side and copy it into your `.env` file.

> [!IMPORTANT]
> You must verify your `DESTINATION_EMAIL` with Cloudflare first as a Destination Address in your Cloudflare Email Routing settings before the API can create rules forwarding to it.

4.  **Create Data Directory**:
    This directory will store the persistent SQLite database for tracking email expiry. Create it in your project root (same level as the `.env` file):

    ```bash
    mkdir data
    ```

5.  **Build the Docker Image**:

    ```bash
    docker build -t cloudflare-temp-email-img .
    ```

6.  **Run the Docker Container**:
    This command runs the container in detached mode (`-d`), maps port 6020, loads your `.env` file, mounts the local `./data` directory into the container for database persistence (`-v`) and names the container. The `--restart=always` flag will make the container restart if it is ever stopped.
    ```bash
    docker run -d \
      --restart=always \
      -p 6020:6020 \
      --env-file .env \
      -v "$(pwd)/data":/app/data \
      --name cloudflare-temp-email \
      cloudflare-temp-email-img
    ```

The API should now be running and accessible at `http://<your_server_ip>:6020`.

### Usage

The API provides the following endpoints:

**Generate an email address:**

Without expiry or comment:

```bash
curl http://localhost:6020/generate
```

With comment:

```bash
curl "http://localhost:6020/generate?comment=test"
```

With expiry (e.g., 1 hour, 2 days, 30 minutes). Minimum expiry is 5 minute.

```bash
# Expires in 1 hour
curl "http://localhost:6020/generate?expiry=1h"

# Expires in 2 days
curl "http://localhost:6020/generate?expiry=2d"

# Expires in 30 minutes
curl "http://localhost:6020/generate?expiry=30m"

# Error - Too short
curl "http://localhost:6020/generate?expiry=1m"
```

_Successful Response (200 OK):_

```json
{
  "comment": "test",
  "email": "random_word123@yourdomain.com",
  "expires_at": "2025-04-06T12:30:00.123456+00:00" // or null if no expiry
}
```

_Error Response (e.g., 400 Bad Request for invalid expiry):_

```json
{
  "error": "Minimum expiry duration is 10 minutes. Requested: '5m'"
}
```

**List all generated email addresses** (created by this API instance):

```bash
curl http://localhost:6020/list
```

_Response (200 OK):_

```json
{
  "generated_emails": [
    {
      "email": "random1_word456@yourdomain.com",
      "comment": "test"
    },
    {
      "email": "random2_word789@yourdomain.com",
      "comment": "none"
    }
  ]
}
```

**Delete an email address rule:**

```bash
curl -X DELETE http://localhost:6020/remove/random1_word456@yourdomain.com
```

_Successful Response (200 OK):_

```json
{
  "message": "Successfully removed rule for random1_word456@yourdomain.com"
}
```

_Error Response (e.g., 404 Not Found):_

```json
{
  "error": "Rule for email random1_word456@yourdomain.com not found"
}
```

**Health Check:**

```bash
curl http://localhost:6020/health
```

_Response (200 OK):_

```json
{
  "status": "healthy"
}
```

**Automatic Cleanup:** A background job runs every 5 minutes (by default) inside the container to check for emails in the local database that have passed their expiry time. If found, it attempts to delete the corresponding rule from Cloudflare and removes the entry from the database.

### Installation for Local Development

##### Prerequisites

- Python 3.10+
- `pip` and `venv`

##### Setup Steps

1.  **Clone & Setup `.env`**: Follow steps 1 & 2 from the Docker deployment instructions (clone repo, create and fill `.env`). Also get your Cloudflare credentials as described above.

2.  **Create Virtual Environment & Install Dependencies**:

    ```bash
    python -m venv venv
    source venv/bin/activate  # on Windows use `venv\Scripts\activate`
    pip install -r requirements.txt
    ```

3.  **Create Data Directory**: The local database will be stored here.

    ```bash
    mkdir data
    ```

4.  **Run the API**:
    ```bash
    python app.py
    ```
    The API will run directly on your machine, accessible at `http://localhost:6020` (or the port specified in `.env`). The `emails.db` file will be created inside the `./data` directory.

### License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
