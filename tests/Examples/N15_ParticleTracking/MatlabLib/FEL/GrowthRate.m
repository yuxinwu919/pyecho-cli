function [growth_rate u_max field_gain]=GrowthRate(u,dz)
 [u_maxs ind_max]=max(u);
 LL=gradient(log(abs(u/u(1))),dz);
 uc=u(ind_max); ind2=ind_max;
 uc2=uc*0.3;
 while (uc>uc2)&(ind2>1)
        ind2=ind2-1;
        uc=u(ind2);
 end;
 
 uc=u(ind2); ind1=ind2;    uc2=uc*0.05;
 while (uc>uc2)&(ind1>1)
        ind1=ind1-1;
        uc=u(ind1);
 end;

 growth_rate=sum(LL(ind1:ind2))/(ind2-ind1+1);
 u_max=u_maxs;
 field_gain=u_max/u(1);
    