function [xxs,Eref]=xpx2xxs_igor(xpx,Eref_in)
PhysConsts;
xxs=xpx;
xxs(:,4)=xpx(:,4)./xpx(:,6);
xxs(:,5)=xpx(:,5)./xpx(:,6);
h=E_ele_eV*E_ele_eV;

xxs(:,6)=E_ele_eV*sqrt((xpx(:,4).*xpx(:,4)+xpx(:,5).*xpx(:,5) ...
    +xpx(:,6).*xpx(:,6))/h+1);

if nargin==2,
    Eref=Eref_in;
else
    Eref=xxs(1,6);
end

xxs(:,6)=xxs(:,6)/Eref-1;

