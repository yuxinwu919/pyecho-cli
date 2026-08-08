clear all; close all;
%%%%%%%%% Here we difine form function (it can be any function)
x=[0:0.01:50]*1e-3;
n=length(x);
y(1:n)=0;
for i=1:n,
    if (x(i)>1e-3) && (x(i)<=30e-3),
        y(i)=x(i)-1e-3;
    end;
end;
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
