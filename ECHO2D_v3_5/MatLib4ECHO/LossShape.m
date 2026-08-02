% loss, spread, peak 
% dimensions: 
%             wake - m , Volt/pC
%             out - V/pC;  
function [loss,spread, peak]=LossShape(bunch,wake)
nw=max(abs(wake(:,2)));
w=wake(:,2);
n=length(w);
bi2(1:n,1)=0;
nb=length(bunch(:,2));
bi2(1:nb)=bunch(:,2);
h=wake(2,1)-wake(1,1);
loss=-bi2'*w*h;
spread=sqrt(bi2'*(w+loss).^2*h);
peak=max(abs(w));



