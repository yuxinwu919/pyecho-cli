function [mx my mxx mxy myy emitt inds]=Moments(x,y,cut)
% [mx my mxx mxy myy emitt]=Moments(x,y,cut)
if nargin<3, cut=0; end;
n=length(x); inds=[1:n];
mx=mean(x); my=mean(y);
x=x-mx; y=y-my;
x2=x.*x; mxx=sum(x2)/n;
y2=y.*y; myy=sum(y2)/n;
xy=x.*y; mxy=sum(xy)/n;

emitt=sqrt(mxx*myy-mxy*mxy);

if cut>0,
    inds=[];
    beta=mxx/emitt; gamma=myy/emitt;
    alpha=mxy/emitt;
    emittp=gamma*x2+2*alpha*xy+beta*y2;
    [emittp inds0]=sort(emittp);
    n1=round(n*(100-cut)/100);
    inds=inds0(1:n1);
    mx=mean(x(inds)); my=mean(y(inds));
    x1=x(inds)-mx; y1=y(inds)-my;
    mxx=sum(x1.*x1)/n1;
    myy=sum(y1.*y1)/n1;
    mxy=sum(x1.*y1)/n1;
    emitt=sqrt(mxx*myy-mxy*mxy);
end;
    