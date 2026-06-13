drop database if exists satilite;
create database satilite;
use satilite;

create table users (
    id INT PRIMARY KEY AUTO_INCREMENT, 
    name VARCHAR(225),
    phone VARCHAR(10),
    email VARCHAR(50), 
    password VARCHAR(50)
    );
