function M=MfromTwiss(Tw1,Tw2)
% Transport matrix M for two sets of Twiss parameters (alpha,beta,psi)
b1=Tw1(2); a1=Tw1(1); psi1=Tw1(3);
b2=Tw2(2); a2=Tw2(1); psi2=Tw2(3);
psi=psi2-psi1;
cosp=cos(psi);sinp=sin(psi);
M(1:2,1:2)=0;
M(1,1)=sqrt(b2/b1)*(cosp+a1*sinp);          M(1,2)=sqrt(b2*b1)*sinp;
M(2,1)=((a1-a2)*cosp-(1+a1*a2)*sinp)/sqrt(b2*b1);
M(2,2)=sqrt(b1/b2)*(cosp-a2*sinp); 