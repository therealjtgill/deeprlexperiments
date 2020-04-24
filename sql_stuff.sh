#!/bin/bash
# Start the mysql server
mysql -u main_username -p
# Then enter password, you'll get a mySQL Prompt

# To show a list of databases:
show databases;

# Note that you have to USE a database before you can access
# tables within that database
use database_name;

# Show users that are part of this installation of mysql
SELECT User FROM mysql.user;
select user, db, host from mysql.db;

# Change a user's username
alter user 'username'@'hostname' identified by 'newpassword';

# Add a new user
create user 'username'@'hostname' identified by 'newpassword';

# Grant privileges to the new user
grant all privileges on db_name.table_name to 'username'@'hostname';

# Delete a user
drop user [if exists] username;

# Add table to database
create table table_name(column_name type, column_name type, column_name type);
# Valid types are int, varchar(32), float, etc.

# Delete a table from a database
drop table [if exist] tablename;

# List all of the tables in a particular database
from dbname show tables;
