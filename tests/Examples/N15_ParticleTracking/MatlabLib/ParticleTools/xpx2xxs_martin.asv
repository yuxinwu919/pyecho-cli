function [xxs,Eref]=xpx2xxs_martin(xpx,Eref_in)
PhysConsts_martin;
[Np,m]=size(xpx);
xxs=xpx;
xxs(:,4)=xpx(:,4)./xpx(:,6);
xxs(:,5)=xpx(:,5)./xpx(:,6);
Eav=0.0; h=E_ele_eV*E_ele_eV;
for n=1:Np
    xxs(n,6)=E_ele_eV*sqrt((xpx(n,4:6)*xpx(n,4:6)')/h+1);
    Eav=Eav+xxs(n,6);
end
Eav=Eav/Np;
if Eref_in>0
    Eref=Eref_in;
else
    Eref=Eav;
end
for n=1:Np
    xxs(n,6)=xxs(n,6)/Eref-1;
end
