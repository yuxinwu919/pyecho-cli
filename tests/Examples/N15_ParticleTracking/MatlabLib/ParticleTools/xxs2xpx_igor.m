function xpx=xxs2xpx_igor(xxs,Eref,zref)
PhysConsts;
xpx=xxs;
h=Eref/E_ele_eV;
pz=E_ele_eV*sqrt( (((1+xxs(:,6))*h).^2-1)./(1 ...
   +xxs(:,4).*xxs(:,4)+xxs(:,5).*xxs(:,5)) );
xpx(:,4)=xxs(:,4).*pz;
xpx(:,5)=xxs(:,5).*pz;
xpx(:,6)=pz;
xpx(:,3)=xpx(:,3)+zref;




