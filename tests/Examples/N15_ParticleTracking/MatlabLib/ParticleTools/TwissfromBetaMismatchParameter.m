function [M,fi]=BetaMismatchParameter(alpha_e,beta_e,alpha_m,beta_m)
n=length(beta_e);
M(1:n,1)=1.0;gamma(1:n,1)=0;
I=find(beta_e~=0);
beta=beta_e./beta_m;
alpha=alpha_e-alpha_m.*beta;
gamma(I)=(1+alpha(I).^2)./beta(I);
M(I)=0.5*(beta(I)+gamma(I)+sqrt((beta(I)+gamma(I)).^2-4));

I=[];
fi(1:n,1)=0;
I=find(M>1.0001);
fi(I)=0.5*atan2(-2*alpha(I),beta(I)-gamma(I));
I=[];
I=find(fi<0);
fi(I)=fi(I)+pi;
