clear all; close all;
%%%%%%%%% Here we difine form function (it can be any function)
tfactor=1;
T=220e9; c0=299792458;
L=c0/T*tfactor*100; % in cm
xfactor=0.2;
yfactor=0.2;
x=[0:0.001:1]*L*1.5;
n=length(x);
y(1:n)=0;
x0=L*xfactor;
for i=1:n,
    if (x(i)>0) && (x(i)<=x0),
        y(i)=yfactor;
    else
        if (x(i)>x0) && (x(i)<=L),
            y(i)=(x(i)-x0)/(L-x0)*(1-yfactor)+yfactor;
        end;
    end;
end;
x=x+2e-3; %small shift to have the whole "smoothed" shape in window
%%%%%%%%%%% end of form factor definition %%%%%%%%%%%%%%%%%%
pdf=y/sum(y);
cdf=cumsum(pdf);
[cdf,mask]=unique(cdf);
X=x(mask);

Npz=100000;   % number of particles 
ds=1/Npz;
Particles(1:Npz,1)=0;
for i=1:Npz,
    Particles(i,1)=(i-0.5)*ds;   
end;
% convert the uniform to the desired
Particles = interp1(cdf, X,Particles);

hist(Particles(:,1),1000);
ff=fopen('ECHO2D\particles.in','w');
fwrite(ff,Npz,'double');
fwrite(ff,Particles,'double');
fclose(ff);
