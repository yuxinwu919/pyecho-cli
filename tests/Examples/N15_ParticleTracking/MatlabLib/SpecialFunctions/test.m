x=[-0.99:0.01:0.99];
y=erf(x);
plot(x,y);
pause;
y1=derf(x);
plot(x,y-y1);