function [dV dfi]=FindVFiCorrections(P1,P0,k,fi,V,parN,bounds)
[z1 E1]=SliceAnalysis2D (P1,100);
[z1 ind]=unique(z1);E1=E1(ind);
[z0 E0]=SliceAnalysis2D (P0,100);
[z0 ind]=unique(z0);E0=E0(ind);
m0=mean(P1(:,1)); sig0=std(P1(:,1)-m0);
B=s_to_cur(P1(:,1),0.1*sig0,1,1);

bmin=m0+sig0*bounds(1); bmax=m0+sig0*bounds(2)
p0=max(min(z0),min(z1));p0=max(p0, bmin);
p1=min(max(z0),max(z1));p1=min(p1, bmax);

dp=p1-p0;
n=30;
dx=(p1-p0)/n;
x=[0:(n-1)]*dx+p0+dx/2;
y1=interp1(z1,E1,x);
y0=interp1(z0,E0,x);
ro=interp1(B(:,1),B(:,2),x);
dV=0; dfi=0;
if parN==2,
    par=fminsearch(@Optim2,[dV dfi]);
else
    par=fminsearch(@Optim1,dV);
end;
    
 function rez=Optim1(P)
 dV=P(1);
 y2=y0+dV.*cos(k*x+fi);
 rez=mean(abs(y2-y1).*ro),
 plot(x,y1,x,y2);pause(0.02);
 end
  

 function rez=Optim2(P)
 dV=P(1);dfi=P(2);
 y2=y0-V*cos(k*x+fi)+(V+dV).*cos(k*x+fi+dfi);
 rez=mean(abs(y2-y1).*ro),
 plot(x,y1,x,y2);pause(0.02);
 end



end



