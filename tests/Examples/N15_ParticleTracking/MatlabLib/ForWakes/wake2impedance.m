%Fourier transform with exp(iwt)             
%             s    - Meter
%             w -    V/C
%             f -    Hz
%             y -    Om
function [f y] = wake2impedance(s,w);
c=299792458; %light velocity
t0=s(1)/c; 
ds=s(2)-s(1);
dt=ds/c;
n=length(s);
t =s/c;
f= 1/dt*(0:n-1)/n;
shift=exp(i*f*t0*2*pi);
%shift=0;
y=dt*fft(w,n).*shift;


