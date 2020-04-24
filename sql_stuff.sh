#!/bin/bash
# Start the mysql server
mysql -u main_username -p
# Then enter password, you'll get a mySQL Prompt

# To show a list of databases:
mysql> show databases;

# Show users that are part of this installation of mysql
mysql> SELECT User FROM mysql.user;
mysql> select user, db, host from mysql.db;

# Change a user's username
mysql> alter user 'username'@'hostname' identified by 'newpassword';

# Add a new user
mysql> create user 'username'@'hostname' identified by 'newpassword';

# Grant privileges to the new user
grant all privileges on db_name.table_name to 'username'@'hostname';

# Add table to database
create table table_name(column_name type, column_name type, column_name type)
# Valid types are int, varchar(32), float, etc.
