function d=FWHM(x,y,n,iter)
if nargin<4, iter=1; end;
y1=SimpleFilter(y,n,iter);
[my1 i0]=max(y1);
d=0;
if my1>0,
y1=y1/my1; y=y/my1;
plot(x,y,x,y1)
m=0.5;
start=1;
ny=length(y1);
for i=1:ny,
    if y1(i)>m, start=i; break; end;
end;
stop=start;
for i=ny:-1:start,
    if y1(i)>m, stop=i; break; end;
end;

i1=max([start-1 1]);
x0=interp1(y1([i1 start]),x([i1 start]),m);
i1=min([stop+1 ny]);
x1=interp1(y1([stop i1]),x([stop i1]),m);

d=abs(x1-x0);
hold on;
plot([x(start) x(start) x(stop) x(stop)],[0 m m 0],'r','LineWidth',3);
hold off;
pause(0.1)
end;

