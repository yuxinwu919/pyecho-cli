%Fourier transform with exp(-iwt)             
%             f -    Hz
%             y -    Om
%             s    - Meter
%             w -    V/C
function [s w] = impedance2wake(f,y);
c=2.99792458e+8; %light velocity
df=f(2)-f(1);
n=length(f);
s= 1/df*(0:n-1)/n*c;
w=n*df*ifft(y,n,'symmetric');
%w=n*df*ifft(y,n);
