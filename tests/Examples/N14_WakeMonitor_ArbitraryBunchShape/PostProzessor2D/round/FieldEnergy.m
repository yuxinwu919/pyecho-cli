clear all; close all;
% the units and the conversion factors are not up to date. To be corrected.
% 01.03.2020
PhysConsts;
ff=fopen('../../ECHO2D/round/Field_00.bin','r'); 
K=1;
hy=0.00098591549295775;
hz=0.001;
eps=1;
a=1;

p=fread(ff,2,'long');nx0=p(1); ny0=p(2);
Ex1=fread(ff,[ny0,nx0],'double');
Ey1=fread(ff,[ny0,nx0],'double');
Ez1=fread(ff,[ny0,nx0],'double');
Hx1=fread(ff,[ny0,nx0],'double');
Hy1=fread(ff,[ny0,nx0],'double');
Hz1=fread(ff,[ny0,nx0],'double');
fclose(ff);
hy05=hy*0.5;
[n m]=size(Ex1);
R=[0:n-1]*hy;
Z=[0:m-1]*hz;
indR=[2:n];
indZ=[1:m];

mesh(R(indR)*1e3,Z(indZ)*1e3,Hz1(indR,indZ)');
view(-90,90);

Ex2=Ex1.*Ex1; Ey2=Ey1.*Ey1; Ez2=Ez1.*Ez1;
WE=0;
for i=indR,
    koef=1;
    if (R(i)>a) koef=eps; end;
    WE=WE+sum(R(i)*Ey2(i,indZ))*koef;
    WE=WE+sum((R(i)-hy05)*Ex2(i,indZ))*koef;
    WE=WE+sum(Ez2(i,indZ)/(R(i)-hy05))*koef;
end;
WE=K*pi*eps0*WE*hy*hz*c*c;

Hx2=Hx1.*Hx1; Hy2=Hy1.*Hy1; Hz2=Hz1.*Hz1;
WH=0;
for i=indR,
    WH=WH+sum(R(i)*Hx2(i,indZ));
    WH=WH+sum((R(i)-hy05)*Hy2(i,indZ));
    WH=WH+sum(Hz2(i,indZ)/R(i));
end;
WH=K*pi/mue0*WH*hy*hz;

W=(WE+WH)*1e3 %J->mJ
P=W/Z(end)*c*2*1e-3



