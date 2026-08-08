function [xpx,Tr]=xpt2xpx_martin(xpt,Zr,Tr_in)
% function [xpx,Tr]=xpt2xpx_martin(xpt,Zr,Tr_in)
% xpt = [x  xs y  ys t  ga*be]@Zr
% Tr  = time of all particles
% xpx = [x  y  z  px py pz   ]@Tr
if nargin==2
    Tr=mean(xpt(:,5));
else
    Tr=Tr_in;
end
PhysConsts_martin;
[Np,m]=size(xpt); xpx(Np,6)=0.0;
for n=1:Np
    h=sqrt(1+xpt(n,2)^2+xpt(n,4)^2);
    gabe=xpt(n,6);
    p=gabe*E_ele_eV;
    v=c*gabe/sqrt(gabe*gabe+1);
    xpx(n,4)=p*xpt(n,2)/h;
    xpx(n,5)=p*xpt(n,4)/h;
    xpx(n,6)=p/h;
    deltaz=(Tr-xpt(n,5))*v/h;
    xpx(n,1)=xpt(n,1)+xpt(n,2)*deltaz;
    xpx(n,2)=xpt(n,3)+xpt(n,4)*deltaz;
    xpx(n,3)=Zr+deltaz;
end
