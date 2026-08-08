function [r56 t566 u5666 Sref]=R56fromR(LB,LD,r,type)
 r56=0; t566=0; u5666=0;
 if type=='c'
   [r56 t566 u5666 Sref]=R56(LB,LD,r,4); 
 else
   if type=='s'
      [r56 t566 u5666 Sref]=R56(LB,2*LD+dx(r,LB),r,6); 
   end;
 end;    

function rez=dx(r,LB)
  LB2=LB*LB;r2=r*r;
  rez=sqrt(1-LB2/r2)*r*(r-sqrt(r2-LB2))/LB;


function [r56 t566 u5666,Sref]=R56(LB,LD,r,m)
   LB2=LB*LB;r2=r*r;
   K=sqrt(1-LB2/r2);
   r56=m*r*asin(LB/r)-m*LB/K-2*LB2*LD/(K^3*r2);
   t566=( r2*LB2*(6*LD+m*LB)-m*LB^5 )/(2*K*(LB2-r2)^2);
   p1=m*LB^7-LB^4*(5*m*LB-6*LD)*r2+4*LB2*(6*LD+m*LB)*r^4;
   p2=6*K*(LB2-r2)^3;
   u5666=p1/p2;
   Sref=m*r*asin(LB/r) + 2*LD/cos(asin(LB/r));
   


