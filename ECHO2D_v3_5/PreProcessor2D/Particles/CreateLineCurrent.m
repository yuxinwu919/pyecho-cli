%the script creates a Gussian line current profile
clear all; close all;
path('../../../MatLib4ECHO',path);

dir_out='../ECHO2D/';
sigma=0.0005; %meters
s=[-5:0.2:5]*sigma;
ro=gauss(s,sigma);
s=s-s(1);

filename=[dir_out 'LineCurrent.txt'];
fileID = fopen(filename,'w');
fprintf(fileID,'%% z[m]  	 charge [normalized]\n');
fprintf(fileID,'%16.7e %16.7e\n',[s' ro']');
fclose(fileID);

out=load(filename);
plot(out(:,1),out(:,2))
