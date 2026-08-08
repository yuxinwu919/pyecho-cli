function inds=CutBadParticles(x1,y1,z1,cut,bounds,rep)
 cut0=(1-power(1-cut/100,1/rep))*100;
 n=length(z1);
 inds=[1:n];
 for i=1:rep,
    x=[];y=[];z=[];inds0=[];emittp=[];inds1=[];
    x=x1(inds); y=y1(inds);z=z1(inds);
    z0=mean(z); sig0=std(z);
    inds0=find(z>z0+sig0*bounds(1) & z<z0+sig0*bounds(2));
    [mx my mxx mxy myy emitt]=Moments(x(inds0),y(inds0));
    beta=mxx/emitt; gamma=myy/emitt;    alpha=-mxy/emitt;
    x=x-mx;y=y-my;
    emittp=gamma*x.*x+2*alpha*x.*y+beta*y.*y;
    inds0=[];n=length(emittp);
    [emittp inds0]=sort(emittp);
    n1=round(n*(100-cut0)/100);
    inds1=inds(inds0(1:n1));inds=[]; inds=inds1;
    plot(x1,y1,'b.','MarkerSize',5);hold on;
    plot(x1(inds),y1(inds),'r.','MarkerSize',4);hold off;
    pause(0.1);
end;