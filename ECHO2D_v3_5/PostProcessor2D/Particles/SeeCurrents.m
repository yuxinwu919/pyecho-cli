clear all; close all;
Iz=load('round\Iz.txt');
Ir=load('round\Ir.txt');
subplot(2,1,1);
mesh(Iz(30:110,2:30));
subplot(2,1,2);
mesh(Ir(30:110,2:30));