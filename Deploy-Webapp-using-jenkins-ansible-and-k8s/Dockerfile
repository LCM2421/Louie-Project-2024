FROM ubuntu:latest

# Set maintainer information
LABEL maintainer="louiepython2023@gmail.com"

# Update package lists and install required packages
RUN apt-get update && \
    apt-get install -y apache2 zip unzip && \
    apt-get clean

# Add website content
ADD https://www.free-css.com/assets/files/free-css-templates/download/page296/finexo.zip /var/www/html/

# Set working directory
WORKDIR /var/www/html/

# Unzip website content and clean up
RUN unzip finexo.zip -d finexo && \
    cp -rvf finexo/* . && \
    rm -rf finexo finexo.zip

# Expose port 80
EXPOSE 80

# Start Apache HTTP Server
CMD ["apache2ctl", "-D", "FOREGROUND"]
