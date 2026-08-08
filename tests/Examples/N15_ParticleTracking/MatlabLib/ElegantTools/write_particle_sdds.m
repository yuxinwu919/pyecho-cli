function [] = write_particle_sdds(filename,xpt,Charge,description,idx)
%function [] = write_particle_sdds(filename,xpt,Charge,{description,{idx}})
%   Detailed explanation goes here
if nargin<3
    error('Not enough input arguments - make_particle_sdds');
end
if nargin==3, description='no description'; end
L_idx=(nargin>=5);

Step=1;
pCentral=mean(xpt(:,5));
[NParticles N6]=size(xpt);
%
f_out=fopen(filename,'wt');
% ........................................................................
fprintf(f_out,'%s\n','SDDS1');
fprintf(f_out,'%s\n',['&description text="' description ...
                      '", contents="output phase space", &end']);
% ... parameter ..........................................................
fprintf(f_out,'%s\n',['&parameter name=Step, description=' ...
                      '"Simulation step", type=long, &end']);
fprintf(f_out,'%s\n',['&parameter name=pCentral, symbol=p$bcen$n, ' ...
                      'units=m$be$nc, description=' ...
                      '"Reference beta*gamma", type=double, &end']);
fprintf(f_out,'%s\n',['&parameter name=Charge, units=C, description=' ...
                      '"Beam charge", type=double, &end']);
fprintf(f_out,'%s\n',['&parameter name=Particles, description=' ...
                      '"Number of particles", type=long, &end']);
% ... column ..............................................................
fprintf(f_out,'%s\n','&column name=particleID, type=long, &end');
fprintf(f_out,'%s\n','&column name=x, units=m, type=double, &end');
fprintf(f_out,'%s\n','&column name=xp, symbol=x'', type=double, &end');
fprintf(f_out,'%s\n','&column name=y, units=m, type=double, &end');
fprintf(f_out,'%s\n','&column name=yp, symbol=y'', type=double, &end');
fprintf(f_out,'%s\n','&column name=t, units=s, type=double, &end');
fprintf(f_out,'%s\n','&column name=p, units=m$be$nc, type=double, &end');
fprintf(f_out,'%s\n','&data mode=ascii, &end');
% ... the only page ......................................................
fprintf(f_out,'%s\n','!page number 1');
% ... parameters
fprintf(f_out,'%i\n',Step);
fprintf(f_out,'%12.8d\n',pCentral);
fprintf(f_out,'%12.8d\n',Charge);
fprintf(f_out,'%i\n',NParticles);
% ... table
fprintf(f_out,'%10i\n',NParticles);
format='%10i %+20.16e %+20.16E %+20.16E %+20.16E %+20.16E %+20.16E\n';
for n=1:NParticles
    if L_idx, i=idx(n); else i=n; end
    fprintf(f_out,format,i,xpt(n,1:6));
end
% ........................................................................
fclose(f_out);
end
