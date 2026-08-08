function [out PD sig00]=Astra2Genesis(astrafile,genfile,Ns,M,sig0,bounds,matchflag,Twiss_x,Twiss_y)
PhysConsts;
[PD Q]=LoadAstraParticles(astrafile); Q=Q*1e-9; 
m0=mean(PD(:,3));PD(:,3)=PD(:,3)-m0; sig00=std(PD(:,3));
PD=xpx2xxs(PD); 
if matchflag, PD=Matching(PD,bounds,Twiss_x,Twiss_y); end ;
PD=Centre(PD,bounds, [1 1 0 1 1 0]);
PD=sortrows(PD,3); [z inds]=unique(PD(:,3));
s0=min(PD(:,3));s1=max(PD(:,3)); 
ds=(s1-s0)/(Ns-1);
s=([1:Ns]-1)*ds+s0; s(Ns)=s1;
out(1:Ns,1:15)=0;
out(:,1)=s;
[mx mxs mxx mxxs mxsxs emittx]=SliceAnalysis (PD(:,3),PD(:,3),PD(:,6),M,false);
out(:,2)=interp1(z,mxs(inds),s,'linear',0)/(me*c*c/e); %gamma
out(:,3)=interp1(z,sqrt(mxsxs(inds)),s,'linear',0)/(me*c*c/e); %delgam
[mx mxs mxx mxxs mxsxs emittx]=SliceAnalysis (PD(:,3),PD(:,1),PD(:,4),M,false);
out(:,4)=interp1(z,emittx(inds),s,'linear',0); %emittx
out(:,6)=interp1(z,mxx(inds),s,'linear',0);out(:,6)=out(:,6)./out(:,4); %betax
out(:,8)=interp1(z,mx(inds),s,'linear',0); out(:,8)=out(:,8);% xbeam
out(:,10)=interp1(z,mxs(inds),s,'linear',0);out(:,10)=out(:,10).*out(:,2); out(:,10)=out(:,10); %pxbeam
out(:,12)=interp1(z,mxxs(inds),s,'linear',0);out(:,12)=-out(:,12)./out(:,4); %alphax
out(:,4)=out(:,4).*out(:,2);
[mx mxs mxx mxxs mxsxs emittx]=SliceAnalysis (PD(:,3),PD(:,2),PD(:,5),M,false);
out(:,5)=interp1(z,emittx(inds),s,'linear',0); %emitty
out(:,7)=interp1(z,mxx(inds),s,'linear',0);out(:,7)=out(:,7)./out(:,5); %betay
out(:,9)=interp1(z,mx(inds),s,'linear',0); out(:,9)=out(:,9); % ybeam
out(:,11)=interp1(z,mxs(inds),s,'linear',0);out(:,11)=out(:,11).*out(:,2); out(:,11)=out(:,11); %pybeam
out(:,13)=interp1(z,mxxs(inds),s,'linear',0);out(:,13)=-out(:,13)./out(:,5); %alphay
out(:,5)=out(:,5).*out(:,2);
sig1=sig0*sig00;
B=s_to_cur(PD(:,3),sig1,Q,c);
out(:,14)=interp1(B(:,1),B(:,2),s,'linear',0); % I
out(:,1)=s;
fid = fopen(genfile,'wt');
fprintf(fid,'#\n? VERSION = 1.0\n');
fprintf(fid,'? SIZE =%ld\n',Ns);
fprintf(fid,'? COLUMNS ZPOS GAMMA0 DELGAM EMITX EMITY BETAX BETAY XBEAM YBEAM PXBEAM PYBEAM ALPHAX ALPHAY CURPEAK ELOSS\n');
fprintf(fid,'%g %g %g %g %g %g %g %g %g %g %g %g %g %g %g\n',out');
fclose(fid);

