%Impedance assembling
clear all;close all;
path('../../../../MatLib4ECHO',path);
PhysConsts;
dir_in='../../ECHO1D/';
dir_out=dir_in;

filename='Impedance_M000.txt';
Zm=load([dir_in filename]);
K=Zm(:,1);
nK=length(K);
ZL=(Zm(:,2)+1i*Zm(:,3));
ZQ=Zm(:,4)+1i*Zm(:,5);
filename='Impedance_M001.txt';
Zm=load([dir_in filename]);
ZD=Zm(:,4)+1i*Zm(:,5);

f2k=2*pi/c;

out(1:nK,1:7)=0;
out(:,1)=K; 
out(:,2)=real(ZL);
out(:,3)=imag(ZL);
out(:,4)=real(ZQ);
out(:,5)=imag(ZQ);
out(:,6)=real(ZD);
out(:,7)=imag(ZD);

filename=[dir_out 'ImpedanceLQD.txt'];
save(filename,'out','-ascii');
fileID = fopen(filename,'w');
fprintf(fileID,'%% %15s %16s %16s %16s \n','k','Zlong[Omm/m]','Zquad[Omm/m^2]','Zdip[Omm/m^2]');
fprintf(fileID,'%16.7e %16.7e %16.7e %16.7e %16.7e %16.7e %16.7e \n',out');
fclose(fileID);



subplot(3,1,1)
plot(K,real(ZL),K,imag(ZL));ylabel('Zlong[Omm/m]');xlabel('k[1/m]');;xlim([10 10000])
subplot(3,1,2)
plot(K,real(ZQ),K,imag(ZQ));ylabel('Zquad[Omm/m^2]');xlabel('k[1/m]');;xlim([10 1000])
subplot(3,1,3)
plot(K,real(ZD),K,imag(ZD));ylabel('Zdip[Omm/m^2]');xlabel('k[1/m]');;xlim([10 1000])
