clear all; close all;
PhysConsts;
ff=fopen('InField\Field_00.bin','r'); K=1;
p=fread(ff,2,'long');nx1=p(1); ny1=p(2);
Ex1=fread(ff,[ny1,nx1],'double');
Ey1=fread(ff,[ny1,nx1],'double');
Ez1=fread(ff,[ny1,nx1],'double');
Hx1=fread(ff,[ny1,nx1],'double');
Hy1=fread(ff,[ny1,nx1],'double');
Hz1=fread(ff,[ny1,nx1],'double');
fclose(ff);
%ff=fopen('./Fields_in_m00_in.bin','r'); K=1;
ff=fopen('round/Field_00.bin','r'); K=1;
p=fread(ff,2,'long');nx2=p(1); ny2=p(2);
Ex2=fread(ff,[ny2,nx2],'double');
Ey2=fread(ff,[ny2,nx2],'double');
Ez2=fread(ff,[ny2,nx2],'double');
Hx2=fread(ff,[ny2,nx2],'double');
Hy2=fread(ff,[ny2,nx2],'double');
Hz2=fread(ff,[ny2,nx2],'double');
fclose(ff);

F1=Ex1;
F2=Ex2;

figure(1);
subplot(2,1,1);
mesh(F1);
subplot(2,1,2);
mesh(F2);

figure(2);
betaz =0.997084677679532
i0=round((1-betaz)*1000)
i=10;
Z=[1:nx1]; R=[1:ny1];
plot(Z+i0,F1(i,:),Z,F2(i,:))

figure(3);
mesh(F1-F2);
