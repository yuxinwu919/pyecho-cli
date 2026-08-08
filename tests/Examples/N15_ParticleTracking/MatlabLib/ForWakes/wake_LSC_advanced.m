function [res]=wake_LSC_advanced(xb,bunch,z,emit,beta,gamma)

PhysConsts;
nb=length(xb); ds=xb(2)-xb(1);
n=2*nb; 
dt=ds/c; f= 1/dt*(0:n-1)/n;

Za = 1e-12*imp_LSC_advanced(f(1:nb),z,emit,beta,gamma)

for i=1:n,    xb1(i)=xb(1)+(i-1)*ds; end;
bunch1=[bunch' zeros(1,nb)];

[f Zb]=wake2impedance(xb1,bunch1*c);

Z(1:n)=0; Z(1:nb)=Za.*Zb(1:nb); Z(nb+1:n)=flipdim(conj(Z(1:nb)),1);

[xa wa]=impedance2wake(f,Z);
res(:,1)=-wa(1:nb);





