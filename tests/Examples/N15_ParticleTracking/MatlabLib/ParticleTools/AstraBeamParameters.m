function [Q,gamma0,E0,pz0,x_rms,xs_rms]=AstraBeamParameters(PD)
PhysConsts;
Q=sum(PD(:,8))*1e-9; %total charge
Ekin=sqrt(E00*E00+PD(:,4).^2+PD(:,5).^2+PD(:,6).^2)-E00; %kinetic energy
Ekin0=mean(Ekin);
gamma0=Ekin0/(me*c*c)*e+1;
E0=mean(PD(:,6)); %mean energy in eV
pz0=E0*e/c; %mean momentum
x=PD(:,1); pxs=PD(:,4)./PD(:,6);
[mx mxs mxx mxxs mxsxs emitx0]=Moments(x,pxs);  %emit0=sqrt(det(cov(x,pxs)));
x_rms=sqrt(mxx);
xs_rms=sqrt(mxsxs); %divergence 
xxs=mxxs/x_rms; %normalized divergence
emitxn=pz0*emitx0/(me*c) %normalized emmitance
betax_opt=mxx/emitx0 % optical beta function
y=PD(:,2); pxs=PD(:,5)./PD(:,6);
[my mys myy myys mysys emity0]=Moments(x,pxs);  %emit0=sqrt(det(cov(x,pxs)));
y_rms=sqrt(myy);
ys_rms=sqrt(mysys); %divergence 
yys=myys/y_rms; %normalized divergence
emityn=pz0*emity0/(me*c) %normalized emmitance
betay_opt=myy/emity0 % optical beta function