# Purpose: Dockerfile for building the image of the web server
FROM python:3.13-slim

# Set the working directory to /app
WORKDIR /usr/src/app

# Set timezone to Taipei
ENV TZ=Asia/Taipei
RUN ln -snf /usr/share/zoneinfo/"$TZ" /etc/localtime && echo "$TZ" > /etc/timezone

# Install python
COPY requirements.txt .
RUN pip3 install -r requirements.txt --no-cache-dir
COPY . ./

# Run main.py when the container launches
EXPOSE 5000
CMD ["python", "main.py"]
