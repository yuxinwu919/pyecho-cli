function [s,I,ex,ey,se,gamma0,emitxn,emityn]=GlobalSliceAnalysis(PD,q1,Mslice,Mcur,p,iter)
PhysConsts;
PD=sortrows(PD,3); z=PD(:,3);
[mx mxs mxx mxxs mxsxs emittx]=SliceAnalysis (z,PD(:,1),PD(:,4),Mslice,false);
[my mys myy myys mysys emitty]=SliceAnalysis (z,PD(:,2),PD(:,5),Mslice,false);
[mE mEs mEE mEEs mEsEs emittE]=SliceAnalysis (z,PD(:,3),PD(:,6),Mslice,false);
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
ex=SimpleFilter(ex,p,iter)*gamma0*1e6;ey=SimpleFilter(ey,p,iter)*gamma0*1e6;
se=SimpleFilter(se,p,iter);
I=interp1(B(:,1),B(:,2)*1e-9,s);


