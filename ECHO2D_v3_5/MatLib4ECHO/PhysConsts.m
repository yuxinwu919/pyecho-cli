c=2.99792458e8; %m/s
e=1.60217733e-19; %C
me=9.10938188e-31;%kg
eps0=8.854187817e-12; %F/m
mue0=1.2566370614e-6; %H/m
Z0=sqrt(mue0/eps0);
SI=(4*pi*eps0);
IA=me*c*c*c/e*SI;
Esi2gauss=1e-4/(c*1e-8);
grad=pi/180;
E00=me*c*c/e; %rest energy
E_ele_eV=E00;
h_plank=4.135667516e-15; %h/e   eV*s lambda=h*c/E