function [d s0 s1]=FWHM2(x,y,n,iter)
if nargin<4, iter=1; end;
y1=SimpleFilter(y,n,iter);
[my1 i0]=max(y1);
d=0;
if my1>0,
y1=y1/my1; y=y/my1;
plot(x,y,x,y1)
m=0.5;
start=i0;
ny=length(y1);
for i=i0:-1:1,
    if y1(i)<m, start=i; break; end;
end;
stop=i0;
for i=i0:ny,
    if y1(i)<m, stop=i; break; end;
end;

i1=min([start+1 ny]);
x0=interp1(y1([start i1]),x([start i1]),m);
i1=max([stop-1 1]);
x1=interp1(y1([i1 stop]),x([i1 stop]),m);

d=abs(x1-x0);
hold on;
s0=x(start);s1=x(stop);
plot([x(start) x(start) x(stop) x(stop)],[0 m m 0],'r','LineWidth',3);
hold off;
pause(0.1)
end;

