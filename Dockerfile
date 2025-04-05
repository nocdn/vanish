# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir --trusted-host pypi.python.org -r requirements.txt

# Copy the rest of the application code into the container
COPY app.py .
COPY .env.example .

# Make port 6020 available
EXPOSE 6020

# Define environment variables (can be overridden)
ENV FLASK_RUN_PORT=6020
ENV FLASK_DEBUG=false
# REMOVED ENV DATABASE_PATH

# Run app.py when the container launches using Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:6020", "--workers", "2", "app:app"]

# --- Notes on Database Persistence ---
# The application uses a SQLite database located at the fixed path /app/data/emails.db inside the container.
# To make this database persistent across container restarts and accessible
# on your host machine, you MUST mount a host directory to the container's
# /app/data directory when running `docker run`.
#
# Example: To store the database in a 'data' subdirectory of your project root:
# docker run ... -v "$(pwd)/data":/app/data ... <image_name>
#
# Failure to mount a volume will result in database loss when the container stops.