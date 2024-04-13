#/bin/sh

#run this script as root for smooth

printf "\ec"
echo "Updating server"
sleep 3
apt update && apt -y upgrade software-properties-common net-tools git unzip curl
printf "\ec"

install_dir="/var/www/html"
#Creating Random WP Database Credenitals
db_name="wp`date +%s`"
db_user=$db_name
db_password=`date |md5sum |cut -c '1-12'`
sleep 1
mysqlrootpass=`date |md5sum |cut -c '1-12'`
sleep 1

## Install Packages for https and mysql
echo "installing apache2 and mysql server"
sleep 3
apt -y install apache2
apt -y install mysql-server
printf "\ec"

## Start http
rm /var/www/html/index.html

echo "enable apache2 and restart after"
sleep 3
systemctl enable apache2
systemctl start apache2
printf "\ec"

## Start mysql and set root password

echo "enable mysql and start after"
sleep 3
systemctl enable mysql
systemctl start mysql
printf "\ec"

/usr/bin/mysql -e "USE mysql;"
/usr/bin/mysql -e "UPDATE user SET Password=PASSWORD($mysqlrootpass) WHERE user='root';"
/usr/bin/mysql -e "FLUSH PRIVILEGES;"
touch /root/.my.cnf
chmod 640 /root/.my.cnf
echo "[client]">>/root/.my.cnf
echo "user=root">>/root/.my.cnf
echo "password="$mysqlrootpass>>/root/.my.cnf

## Install PHP
echo "Installing all php requirements"
sleep 3
apt -y install php
apt -y install php-mysql
apt -y install php libapache2-mod-php php-mysql
apt -y install php-curl php-gd php-mbstring php-xml php-xmlrpc php-soap php-intl php-zip
printf "\ec"
sed -i '0,/AllowOverride\ None/! {0,/AllowOverride\ None/ s/AllowOverride\ None/AllowOverride\ All/}' /etc/apache2/apache2.conf #Allow htaccess usage

echo "Restarting apache2"
sleep 3
systemctl restart apache2
printf "\ec"

## Download and extract latest WordPress Package
if test -f /tmp/latest.tar.gz
then
echo "WP is already downloaded."
else
echo "Downloading WordPress"
cd /tmp/ && wget "http://wordpress.org/latest.tar.gz";
fi

/bin/tar -C $install_dir -zxf /tmp/latest.tar.gz --strip-components=1
chown www-data: $install_dir -R

#### Create WP-config and set DB credentials
/bin/mv $install_dir/wp-config-sample.php $install_dir/wp-config.php

/bin/sed -i "s/database_name_here/$db_name/g" $install_dir/wp-config.php
/bin/sed -i "s/username_here/$db_user/g" $install_dir/wp-config.php
/bin/sed -i "s/password_here/$db_password/g" $install_dir/wp-config.php

cat << EOF >> $install_dir/wp-config.php
define('FS_METHOD', 'direct');
EOF

cat << EOF >> $install_dir/.htaccess
# BEGIN WordPress
<IfModule mod_rewrite.c>
RewriteEngine On
RewriteBase /
RewriteRule ^index.php$ – [L]
RewriteCond %{REQUEST_FILENAME} !-f
RewriteCond %{REQUEST_FILENAME} !-d
RewriteRule . /index.php [L]
</IfModule>
# END WordPress
EOF

chown www-data: $install_dir -R

## Set WP Salts
echo "creating database and installing wordpress credentials"
sleep 3
grep -A50 'table_prefix' $install_dir/wp-config.php > /tmp/wp-tmp-config
/bin/sed -i '/**#@/,/$p/d' $install_dir/wp-config.php
/usr/bin/lynx --dump -width 200 https://api.wordpress.org/secret-key/1.1/salt/ >> $install_dir/wp-config.php
/bin/cat /tmp/wp-tmp-config >> $install_dir/wp-config.php && rm /tmp/wp-tmp-config -f
/usr/bin/mysql -u root -e "CREATE DATABASE $db_name"
/usr/bin/mysql -u root -e "CREATE USER '$db_name'@'localhost' IDENTIFIED WITH mysql_native_password BY '$db_password';"
/usr/bin/mysql -u root -e "GRANT ALL PRIVILEGES ON $db_name.* TO '$db_user'@'localhost';"
printf "\ec"

## Display generated passwords to log file.
echo "Displaying all creditials of Database"
echo "Database Name: " $db_name
echo "Database User: " $db_user
echo "Database Password: " $db_password
echo "Mysql root password: " $mysqlrootpass
