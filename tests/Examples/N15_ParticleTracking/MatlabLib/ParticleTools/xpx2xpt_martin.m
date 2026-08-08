function [xpt,Zr]=xpx2xpt_martin(xpx,Tr,Zr_in)
% function [xpt,Zr]=xpx2xpt_martin(xpx,Tr,Zr_in)
% xpx = [x  y  z  px py pz   ]@Tr
% Zr  = position of screen
% xpt = [x  xs y  ys t  ga*be]@Zr
if nargin==2
    Zr=mean(xpx(:,3));
else
    Zr=Zr_in;
end
PhysConsts_martin;
[Np,m]=size(xpx); xpt(Np,6)=0.0;
for n=1:Np
    px=xpx(n,4); py=xpx(n,5); pz=xpx(n,6);p=sqrt(px*px+py*py+pz*pz);
    gabe=p/E_ele_eV; vz=c*gabe/sqrt(gabe*gabe+1)*(pz/p);
    xpt(n,2)=px/pz;
    xpt(n,4)=py/pz;
    deltaz=xpx(n,3)-Zr;
    xpt(n,1)=xpx(n,1)-xpt(n,2)*deltaz;
    xpt(n,3)=xpx(n,2)-xpt(n,4)*deltaz;
    xpt(n,5)=Tr-deltaz/vz;
    xpt(n,6)=gabe;
end
