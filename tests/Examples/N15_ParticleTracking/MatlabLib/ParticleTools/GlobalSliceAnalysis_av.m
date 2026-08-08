function [s,I,ex,ey,se,gamma0,emitxn,emityn]=GlobalSliceAnalysis_av(PD,q1,dz,Mcur)
PhysConsts;
PD=sortrows(PD,3); z=PD(:,3);


N=length(z); 
dz05=dz*0.5;
n1a(1:N)=0;n2a(1:N)=0;
mx(1:N)=0.0; mxs(1:N)=0.0; mxx(1:N)=0.0; mxxs(1:N)=0.0; mxsxs(1:N)=0.0;emittx(1:N)=0.0;
my(1:N)=0.0; mys(1:N)=0.0; myy(1:N)=0.0; myys(1:N)=0.0; mysys(1:N)=0.0;emitty(1:N)=0.0;
mE(1:N)=0.0; mEs(1:N)=0.0; mEE(1:N)=0.0; mEEs(1:N)=0.0; mEsEs(1:N)=0.0;
    
 for i =1:1:N,
        i,
        z1=z(i)-dz05;
        z2=z(i)+dz05;
        inds=find(z>=z1& z<=z2);
        n1=inds(1);  n2=inds(length(inds));
        [mx(i) mxs(i) mxx(i) mxxs(i) mxsxs(i),emittx(i)]=Moments(PD(n1:n2,1),PD(n1:n2,4));
        [my(i) mys(i) myy(i) myys(i) mysys(i),emitty(i)]=Moments(PD(n1:n2,2),PD(n1:n2,5));
        [mE(i) mEs(i) mEE(i) mEEs(i) mEsEs(i)]=Moments(PD(n1:n2,3),PD(n1:n2,6));
 end; 


sE=sqrt(mEsEs); 

sig0=std(z);  B=s_to_cur(z,Mcur*sig0,q1,c); 
gamma0=mean(PD(:,6))/E00; 
[mm mm mm mm mm emitty0]=Moments(PD(:,2),PD(:,5));
 emityn=emitty0*gamma0;
[mm mm mm mm mm emitt0]=Moments(PD(:,1),PD(:,4));
emitxn=emitt0*gamma0;

[z ind]=unique(z);emittx=emittx(ind);emitty=emitty(ind);sE=sE(ind);
smin=min(z);smax=max(z);n=1000;hs=(smax-smin)/(n-1);
s=[smin:hs:smax];
ex=interp1(z,emittx,s);ey=interp1(z,emitty,s);se=interp1(z,sE,s);
ex=ex*gamma0*1e6;ey=ey*gamma0*1e6;
I=interp1(B(:,1),B(:,2)*1e-9,s);


