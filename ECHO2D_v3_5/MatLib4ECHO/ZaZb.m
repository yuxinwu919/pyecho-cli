function res=ZaZb(xb,bunch,Za0)
%Za*Zb
hold off;
PhysConsts;
nb=length(xb); ds=xb(2)-xb(1);
n=2*nb; 

dt=ds/c; f= 1/dt*(0:n-1)/n;
f2k=2*pi/c;
[f0 i0]=unique(Za0(:,1));
f0=f0/f2k;
Za=interp1(f0,Za0(i0,2),f(1:nb),'linear',0)+complex(0,1)*interp1(f0,Za0(i0,3),f(1:nb),'linear',0);

for i=1:n,    xb1(i)=xb(1)+(i-1)*ds; end;
bunch1=[bunch' zeros(1,nb)];

[f Zb]=wake2impedance(xb1,bunch1*c);

Z(1:n)=0; Z(1:nb)=Za.*Zb(1:nb); 
Z(nb+1:n)=flipdim(conj(Z(1:nb)),1);

[xa wa]=impedance2wake(f,Z);
res(:,1)=-wa(1:nb);





