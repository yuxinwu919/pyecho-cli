%Impedance assembling
clear all;close all;
path('../../../../MatLib4ECHO',path);
PhysConsts;
Nm=30; 
D=160e-3;gamma=1000; 
dir_in='../../ECHO1D/';
dir_out='../../ECHO1D/';

beta=sqrt(1-1/gamma^2);
filename_format='Impedance_M%03i.txt';
filename=[dir_in sprintf(filename_format,1)];
Zm=load(filename);
kx=pi/D; 
K=Zm(:,1);
nK=length(K);
beta2k=beta./K;
k2beta=K/(beta*gamma^2);
Ky2=(kx*kx*beta2k+k2beta);
ZL=Zm(:,2)+1i*Zm(:,3);
ZQ=(Zm(:,2)+1i*Zm(:,3)).*Ky2;
ZD=(Zm(:,4)+1i*Zm(:,5)).*Ky2;

MagnL(1:Nm)=0;MagnL(1)=sqrt(ZL'*ZL);
MagnQ(1:Nm)=0;MagnQ(1)=sqrt(ZQ'*ZQ);
MagnD(1:Nm)=0;MagnD(1)=sqrt(ZD'*ZD);



for i=2:Nm,
    m=2*i-1;
    kx=pi/D*m;
    filename=[dir_in sprintf(filename_format,m)];
    Zm=load(filename);
    ZL=ZL+Zm(:,2)+1i*Zm(:,3);
    Ky2=(kx*kx*beta2k+k2beta);
    ZQ=ZQ+(Zm(:,2)+1i*Zm(:,3)).*Ky2;
    ZD=ZD+(Zm(:,4)+1i*Zm(:,5)).*Ky2;
    
    MagnL(i)=sqrt(ZL'*ZL);
    MagnQ(i)=sqrt(ZQ'*ZQ);
    MagnD(i)=sqrt(ZD'*ZD);
end;



ZL=ZL*pi/D;
ZQ=ZQ*pi/D;
ZD=ZD*pi/D;

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
plot(K,real(ZL),K,imag(ZL));ylabel('Zlong[Omm/m]');xlabel('k[1/m]');;xlim([10 1000])
subplot(3,1,2)
plot(K,real(ZQ),K,imag(ZQ));ylabel('Zquad[Omm/m^2]');xlabel('k[1/m]');;xlim([10 1000])
subplot(3,1,3)
plot(K,real(ZD),K,imag(ZD));ylabel('Zdip[Omm/m^2]');xlabel('k[1/m]');;xlim([10 1000])

figure();
MagnL=MagnL/max(MagnL);MagnQ=MagnQ/max(MagnQ);MagnD=MagnD/max(MagnD);
plot([1:Nm],MagnL,[1:Nm],MagnQ,[1:Nm],MagnD)
title('How many modes do we need?')
ylabel('V(inf)/V(modes)');xlabel('modes used');

