function z=convolution(u,w)
% convolution of equally spaced functions
hx=u(2)-u(1);
a=u(:,2);
b=w(:,2);
wc(:,1)=conv(a,b)*hx;
nw=length(w(:,1));
nu=length(u(:,1));

x0=u(1,1)+w(1,1);
for i=1:nw+nu-1,    xc(i,1)=x0+(i-1)*hx; end;

z=[xc, wc];


